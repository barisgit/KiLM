"""3D model placement and the model references written into footprints."""

from pathlib import Path

import pytest

from kicad_lib_manager.commands.import_zip.importer import ModelRef, fix_3d_path
from tests.import_zip.helpers import run_import, summary, zip_with

LIB_MODELS = {
    "somepart.stp": ModelRef("${LIB}/SAMPLELIB.3dshapes", "somepart.stp"),
    "somepart.step": ModelRef("${LIB}/SAMPLELIB.3dshapes", "somepart.step"),
    "somepart.stp.gz": ModelRef("${LIB}/SAMPLELIB.3dshapes", "somepart.stp.gz"),
    "somepart.step.gz": ModelRef("${LIB}/SAMPLELIB.3dshapes", "somepart.step.gz"),
}


def _footprint(library_tree: Path, name: str) -> str:
    return (library_tree / "footprints" / "SAMPLELIB.pretty" / name).read_text()


@pytest.mark.parametrize(
    "raw",
    [
        '(model "C:/Vendor/somepart.stp"',
        '(model "C:/Vendor/somepart.step"',
        '(model "C:/Vendor/somepart.stp.gz"',
        '(model "C:/Vendor/somepart.step.gz"',
        '(model "C:\\\\Vendor\\\\3D\\\\SomePart.STEP"',
        "(model somepart.stp",
        "(model somepart.step",
        "(model somepart.stp.gz",
        "(model somepart.step.gz",
        "(model C:/Vendor/SomePart.STP",
        "(model C:/Vendor/SomePart.STEP",
        "(model SomePart.STP.GZ",
        "(model SomePart.Step.gz",
    ],
)
def test_fix_3d_path_points_known_models_at_the_library(raw: str) -> None:
    """Model references to known model files point into the library."""
    # Regression: a misordered alternation matched a compound extension's own
    # prefix ("step" inside "step.gz") and left the rest dangling.
    result = fix_3d_path(raw, LIB_MODELS)

    assert result.startswith('(model "${LIB}/SAMPLELIB.3dshapes/somepart.')
    assert result.count('"') == 2
    assert result.endswith('"')


def test_fix_3d_path_keeps_references_to_other_models() -> None:
    """Model references to unknown files, such as stock models, are unchanged."""
    text = '(model "${KICAD9_3DMODEL_DIR}/Capacitor_SMD.3dshapes/C_0603_1608Metric.wrl"'

    assert fix_3d_path(text, LIB_MODELS) == text


@pytest.mark.usefixtures("mock_config")
def test_footprint_reference_to_a_stock_model_is_kept(
    tmp_path: Path, library_tree: Path
) -> None:
    """An imported footprint keeps its reference to a KiCad stock model."""
    ref = '(model "${KICAD9_3DMODEL_DIR}/Capacitor_SMD.3dshapes/C_0603_1608Metric.wrl"'
    zip_path = zip_with(
        tmp_path, "C", {"C.kicad_mod": f'(footprint "C"\n\t{ref}\n\t)\n)\n'}
    )

    result = run_import(str(zip_path))

    assert result.exit_code == 0, result.output
    assert ref in _footprint(library_tree, "C.kicad_mod")


@pytest.mark.usefixtures("mock_config")
def test_fallback_models_use_library_env_var(
    tmp_path: Path, library_tree: Path
) -> None:
    """Without a 3D library, model paths use kilm.yaml's env_var."""
    (library_tree / "kilm.yaml").write_text(
        "name: mylib\nenv_var: KICAD_LIB_MYLIB\n", encoding="utf-8"
    )
    zip_path = zip_with(
        tmp_path,
        "M1",
        {
            "M1/KiCad/M1.kicad_mod": (
                '(footprint "M1"\n\t(model "C:/x/M1.stp"\n\t)\n)\n'
            ),
            "M1/3D/M1.stp": "STEP",
        },
    )

    result = run_import(str(zip_path))

    assert result.exit_code == 0, result.output
    fp = _footprint(library_tree, "M1.kicad_mod")
    assert '(model "${KICAD_LIB_MYLIB}/SAMPLELIB.3dshapes/M1.stp"' in fp


@pytest.mark.usefixtures("mock_config")
def test_fallback_models_without_env_var_use_absolute_path(
    tmp_path: Path, library_tree: Path
) -> None:
    """Without any env_var, model paths are absolute."""
    zip_path = zip_with(
        tmp_path,
        "M2",
        {
            "M2/KiCad/M2.kicad_mod": '(footprint "M2"\n\t(model "M2.stp"\n\t)\n)\n',
            "M2/3D/M2.stp": "STEP",
        },
    )

    result = run_import(str(zip_path))

    assert result.exit_code == 0, result.output
    fp = _footprint(library_tree, "M2.kicad_mod")
    assert (library_tree / "SAMPLELIB.3dshapes").resolve().as_posix() in fp


@pytest.mark.usefixtures("mock_config")
def test_split_library_fallback_models_dir_named_after_library(
    tmp_path: Path, library_tree: Path
) -> None:
    """A split library's new models dir is named after the KiLM library."""
    (library_tree / "symbols" / "OTHER.kicad_sym").write_text("(kicad_symbol_lib\n)\n")
    zip_path = zip_with(tmp_path, "M3", {"M3/3D/M3.stp": "STEP"})

    result = run_import("-s", "SAMPLELIB", str(zip_path))

    assert result.exit_code == 0, result.output
    assert (library_tree / f"{library_tree.name}.3dshapes" / "M3.stp").exists()
    assert "3D model paths will be absolute to this machine" in result.output


@pytest.mark.usefixtures("mock_config")
def test_models_dir_prefers_library_named_dir(
    tmp_path: Path, library_tree: Path
) -> None:
    """Of several *.3dshapes dirs, the one named after the library is used."""
    (library_tree / "AAA.3dshapes").mkdir()
    (library_tree / "SAMPLELIB.3dshapes").mkdir()
    zip_path = zip_with(tmp_path, "M4", {"M4/3D/M4.stp": "STEP"})

    result = run_import(str(zip_path))

    assert result.exit_code == 0, result.output
    assert (library_tree / "SAMPLELIB.3dshapes" / "M4.stp").exists()
    assert not (library_tree / "AAA.3dshapes" / "M4.stp").exists()


@pytest.mark.usefixtures("mock_config")
def test_model_in_other_models_dir_is_reused(
    tmp_path: Path, library_tree: Path
) -> None:
    """A model already in another *.3dshapes dir is referenced there, not copied."""
    (library_tree / "Aaa.3dshapes").mkdir()
    (library_tree / "Bbb.3dshapes").mkdir()
    (library_tree / "Bbb.3dshapes" / "Part.step").write_text("STEP")
    (library_tree / "kilm.yaml").write_text("name: mylib\nenv_var: KICAD_LIB_MYLIB\n")
    zip_path = zip_with(
        tmp_path,
        "Reuse",
        {
            "R/KiCad/RFP.kicad_mod": (
                '(footprint "RFP"\n\t(model "x/Part.step"\n\t)\n)\n'
            ),
            "R/3D/Part.step": "STEP",
        },
    )

    result = run_import(str(zip_path))

    assert result.exit_code == 0, result.output
    assert (
        "3D   reuse existing ${KICAD_LIB_MYLIB}/Bbb.3dshapes/Part.step for Part.step"
        in result.output
    )
    assert not (library_tree / "Aaa.3dshapes" / "Part.step").exists()
    fp = _footprint(library_tree, "RFP.kicad_mod")
    assert '(model "${KICAD_LIB_MYLIB}/Bbb.3dshapes/Part.step"' in fp


def test_registered_3d_library_receives_models(
    tmp_path: Path, category_tree: Path
) -> None:
    """A 3D library registered inside the library receives the models."""
    zip_path = zip_with(
        tmp_path,
        "CatPart",
        {
            "CatPart/KiCad/CatPartFP.kicad_mod": (
                '(footprint "CatPartFP"\n\t(model "C:/x/CatPart.stp"\n\t)\n)\n'
            ),
            "CatPart/3D/CatPart.stp": "STEP",
        },
    )

    result = run_import("-s", "CAT_IC", "-f", "CAT_QFN", str(zip_path))

    assert result.exit_code == 0, result.output
    fp = category_tree / "footprints" / "CAT_QFN.pretty" / "CatPartFP.kicad_mod"
    assert '(model "${KICAD_3D_CAT_MODELS}/CatPart.stp"' in fp.read_text()
    assert (category_tree / "CAT.3dshapes" / "CatPart.stp").exists()
    assert not (category_tree / "CAT_IC.3dshapes").exists()


def test_absolute_paths_from_other_model_dirs_are_warned(
    tmp_path: Path, category_tree: Path
) -> None:
    """Reusing a model from a dir without an env_var warns about absolute paths."""
    (category_tree / "Old.3dshapes").mkdir()
    (category_tree / "Old.3dshapes" / "Legacy.step").write_text("STEP")
    zip_path = zip_with(tmp_path, "W", {"W/3D/New.step": "STEP"})

    result = run_import("-s", "CAT_IC", "-f", "CAT_QFN", str(zip_path))

    assert result.exit_code == 0, result.output
    assert "3D model paths will be absolute to this machine" in result.output


def test_hidden_files_in_model_dirs_are_ignored(
    tmp_path: Path, category_tree: Path
) -> None:
    """Hidden files in model dirs are not treated as models."""
    # A .DS_Store in an extra dir without a library env var must not count as
    # a model (it would trigger the absolute-path warning on its own).
    (category_tree / "Old.3dshapes").mkdir()
    (category_tree / "Old.3dshapes" / ".DS_Store").write_text("x")
    zip_path = zip_with(tmp_path, "H", {"H/3D/New.step": "STEP"})

    result = run_import("-s", "CAT_IC", "-f", "CAT_QFN", str(zip_path))

    assert result.exit_code == 0, result.output
    assert "absolute to this machine" not in result.output


@pytest.mark.usefixtures("library_tree", "mock_config")
def test_dry_run_reports_model_added_earlier_as_skip(tmp_path: Path) -> None:
    """A dry run reports a model an earlier ZIP of the run added as existing."""
    a = zip_with(tmp_path, "a", {"A/3D/Shared.step": "STEP"})
    b = zip_with(tmp_path, "b", {"B/3D/Shared.step": "STEP"})

    result = run_import("--dry-run", str(a), str(b))

    assert result.exit_code == 0, result.output
    assert result.output.count("3D   add: Shared.step") == 1
    assert "3D   skip (exists): Shared.step" in result.output
    assert "reuse existing" not in result.output


@pytest.mark.usefixtures("mock_config")
def test_file_names_differing_only_in_case_are_one_file(
    tmp_path: Path, library_tree: Path
) -> None:
    """Files whose names differ only in case are imported once."""
    # A library must hold the same files on case-sensitive and
    # case-insensitive filesystems, and dry runs must count what real runs add.
    a = zip_with(
        tmp_path,
        "a",
        {"A/KiCad/Foo.kicad_mod": '(footprint "Foo")\n', "A/3D/Foo.stp": "STEP"},
    )
    b = zip_with(
        tmp_path,
        "b",
        {"B/KiCad/foo.kicad_mod": '(footprint "foo")\n', "B/3D/foo.stp": "STEP"},
    )

    dry = run_import("--dry-run", str(a), str(b))
    real = run_import(str(a), str(b))

    assert real.exit_code == 0, real.output
    assert summary(real.output) == [
        "  Symbols   added: 0",
        "  Footprints added: 1",
        "  3D models  added: 1",
    ]
    assert summary(dry.output) == summary(real.output)
    fp_dir = library_tree / "footprints" / "SAMPLELIB.pretty"
    assert [p.name for p in fp_dir.iterdir()] == ["Foo.kicad_mod"]


@pytest.mark.usefixtures("mock_config")
def test_members_differing_only_in_case_import_the_first_everywhere(
    tmp_path: Path, library_tree: Path
) -> None:
    """Of ZIP members differing only in case, the first is imported."""
    # On a case-insensitive filesystem the second member used to overwrite the
    # first during extraction, so platforms imported different geometry.
    zip_path = zip_with(
        tmp_path,
        "case",
        {
            "P/KiCad/Foo.kicad_mod": '(footprint "Foo" (descr "first"))\n',
            "P/KiCad/foo.kicad_mod": '(footprint "foo" (descr "second"))\n',
        },
    )

    result = run_import(str(zip_path))

    assert result.exit_code == 0, result.output
    assert "FP   skip (exists as Foo.kicad_mod): foo.kicad_mod" in result.output
    assert '(descr "first")' in _footprint(library_tree, "Foo.kicad_mod")


@pytest.mark.usefixtures("mock_config")
def test_footprint_extension_is_written_in_lowercase(
    tmp_path: Path, library_tree: Path
) -> None:
    """Footprints are written with the .kicad_mod suffix KiCad lists."""
    # KiCad lists only *.kicad_mod, so Part.KICAD_MOD would be missing from
    # the library on case-sensitive filesystems.
    zip_path = zip_with(
        tmp_path,
        "upper",
        {
            "U/KiCad/U.kicad_sym": (
                '(kicad_symbol_lib\n\t(symbol "U"\n'
                '\t\t(property "Footprint" "Part")\n\t)\n)\n'
            ),
            "U/KiCad/Part.KICAD_MOD": '(footprint "Part")\n',
        },
    )

    result = run_import(str(zip_path))

    assert result.exit_code == 0, result.output
    assert "FP   add: Part.kicad_mod" in result.output
    fp_dir = library_tree / "footprints" / "SAMPLELIB.pretty"
    assert [p.name for p in fp_dir.iterdir()] == ["Part.kicad_mod"]
    sym_text = (library_tree / "symbols" / "SAMPLELIB.kicad_sym").read_text()
    assert '"Footprint" "SAMPLELIB:Part"' in sym_text


@pytest.mark.parametrize("kept_from", ["library", "earlier ZIP"])
@pytest.mark.usefixtures("mock_config")
def test_symbols_reference_the_kept_spelling_of_a_skipped_footprint(
    tmp_path: Path, library_tree: Path, kept_from: str
) -> None:
    """Symbols reference an existing footprint by its name in the library."""
    # On case-sensitive filesystems "SAMPLELIB:foo" would not find Foo.kicad_mod.
    fp_dir = library_tree / "footprints" / "SAMPLELIB.pretty"
    zips = [
        zip_with(
            tmp_path,
            "b",
            {
                "B/KiCad/B.kicad_sym": (
                    '(kicad_symbol_lib\n\t(symbol "B"\n'
                    '\t\t(property "Footprint" "foo")\n\t)\n)\n'
                ),
                "B/KiCad/foo.kicad_mod": '(footprint "foo")\n',
            },
        )
    ]
    if kept_from == "library":
        (fp_dir / "Foo.kicad_mod").write_text('(footprint "Foo")\n')
    else:
        zips.insert(
            0, zip_with(tmp_path, "a", {"A/KiCad/Foo.kicad_mod": '(footprint "Foo")\n'})
        )

    result = run_import(*map(str, zips))

    assert result.exit_code == 0, result.output
    assert "FP   skip (exists as Foo.kicad_mod): foo.kicad_mod" in result.output
    sym_text = (library_tree / "symbols" / "SAMPLELIB.kicad_sym").read_text()
    assert '"Footprint" "SAMPLELIB:Foo"' in sym_text
    assert [p.name for p in fp_dir.iterdir()] == ["Foo.kicad_mod"]
