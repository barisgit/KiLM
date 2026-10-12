#!/usr/bin/env tsx

import fs from 'fs';
import path from 'path';
import chokidar from 'chokidar';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Paths
const rootDir = path.resolve(__dirname, '../..');
const commandsDir = path.join(rootDir, 'kicad_lib_manager', 'commands');
const docsOutputDir = path.join(__dirname, '..', 'src', 'content', 'docs', 'reference', 'cli');

/**
 * Sanitize command name to create safe filenames
 */
function sanitizeCommandName(name: string): string {
  return name.trim().toLowerCase().replace(/[^a-z0-9_-]/g, '-').replace(/-+/g, '-');
}

/**
 * Escape string for safe use in YAML frontmatter
 */
function escapeYaml(s: string): string {
  return s.replace(/\\/g, '\\\\').replace(/"/g, '\\"').replace(/\r?\n/g, ' ');
}

interface CommandDoc {
  commandName: string;
  embeddedPath: string;
  outputPath: string;
}

/**
 * Get the CLI command name for a directory, either from .command file or directory name
 */
function getCommandName(commandDir: string, dirName: string): string {
  const commandFile = path.join(commandDir, '.command');
  
  if (fs.existsSync(commandFile)) {
    try {
      const commandName = fs.readFileSync(commandFile, 'utf-8').trim();
      if (commandName) {
        return sanitizeCommandName(commandName);
      }
    } catch (error) {
      console.warn(`Failed to read .command file for ${dirName}:`, error);
    }
  }
  
  // Fallback to directory name
  return sanitizeCommandName(dirName);
}

/**
 * Find all command directories with embedded docs
 */
function findCommandDocs(): CommandDoc[] {
  if (!fs.existsSync(commandsDir)) {
    console.warn(`Commands directory not found: ${commandsDir}`);
    return [];
  }

  const commandDirs = fs.readdirSync(commandsDir, { withFileTypes: true })
    .filter(dirent => dirent.isDirectory())
    .map(dirent => dirent.name);

  const commandDocs: CommandDoc[] = [];

  for (const dirName of commandDirs) {
    const commandDir = path.join(commandsDir, dirName);
    
    // Check for both .mdx and .md files
    const mdxPath = path.join(commandDir, 'docs.mdx');
    const mdPath = path.join(commandDir, 'docs.md');
    
    let docsPath: string | null = null;
    if (fs.existsSync(mdxPath)) {
      docsPath = mdxPath;
    } else if (fs.existsSync(mdPath)) {
      docsPath = mdPath;
    }
    
    if (docsPath) {
      // Get the CLI command name (from .command file or directory name)
      const commandName = getCommandName(commandDir, dirName);
      
      // Preserve the original file extension
      const extension = path.extname(docsPath);
      commandDocs.push({
        commandName,
        embeddedPath: docsPath,
        outputPath: path.join(docsOutputDir, `${commandName}${extension}`)
      });
    }
  }

  return commandDocs;
}

/**
 * Process MDX content and add proper frontmatter if needed
 */
function processEmbeddedDoc(content: string, commandName: string): string {
  // Strip UTF-8 BOM if present
  const cleanContent = content.replace(/^\uFEFF/, '');
  
  // Check if content already has frontmatter
  const frontmatterMatch = cleanContent.match(/^---\n([\s\S]*?)\n---\n([\s\S]*)$/);
  
  if (frontmatterMatch) {
    // Content already has frontmatter, return as-is
    return cleanContent;
  }
  
  // No frontmatter, add it
  // Extract title from first heading or use command name
  const titleMatch = cleanContent.match(/^# (.+)$/m);
  const title = titleMatch ? titleMatch[1] : commandName;
  
  // Extract description from content or use default
  const descriptionMatch = cleanContent.match(/^(.+)$/m);
  const firstLine = descriptionMatch ? descriptionMatch[1].replace(/^# /, '') : '';
  const description = firstLine || `${commandName} command documentation`;

  // Create frontmatter with properly escaped values
  const frontmatter = `---
title: "${escapeYaml(title)}"
description: "${escapeYaml(description)}"
sidebar:
  label: "${escapeYaml(commandName)}"
---

`;

  // Remove the first heading since it's now in frontmatter
  const contentWithoutTitle = cleanContent.replace(/^# .+$/m, '').trim();
  
  return frontmatter + contentWithoutTitle;
}

/**
 * Sync a single embedded doc to the output directory.
 * Errors propagate so a one-shot sync (and therefore the build) fails instead of
 * publishing a site with a missing command page.
 */
function syncDoc(commandDoc: CommandDoc): void {
  const content = fs.readFileSync(commandDoc.embeddedPath, 'utf-8');
  const processedContent = processEmbeddedDoc(content, commandDoc.commandName);
  fs.mkdirSync(path.dirname(commandDoc.outputPath), { recursive: true });
  fs.writeFileSync(commandDoc.outputPath, processedContent);
  console.log(`Synced ${path.basename(commandDoc.outputPath)}`);
}

/**
 * Sync all embedded docs to the output directory
 */
function syncAllDocs(): void {
  console.log('Syncing embedded documentation...');

  const commandDocs = findCommandDocs();
  if (commandDocs.length === 0) {
    throw new Error(`No embedded docs found under ${commandsDir}`);
  }

  for (const commandDoc of commandDocs) {
    syncDoc(commandDoc);
  }

  console.log(`Synced ${commandDocs.length} embedded docs`);
}

/** File names inside a command directory that affect the generated pages. */
const DOCS_SOURCE_FILES = new Set(['docs.mdx', 'docs.md', '.command']);

/**
 * Watch the commands directory and re-sync on any change to a docs source.
 * chokidar 4+ no longer expands globs, so the directory itself is watched and
 * other files are filtered out. Re-syncing everything is cheap (one small file
 * per command) and also covers renames, new commands, and `.command` changes.
 */
function watchDocs(): void {
  cleanupDocs();
  syncAllDocs();

  const watcher = chokidar.watch(commandsDir, {
    ignoreInitial: true,
    ignored: (filePath, stats) =>
      stats?.isFile() === true && !DOCS_SOURCE_FILES.has(path.basename(filePath)),
  });

  watcher
    .on('all', (event, filePath) => {
      if (event === 'addDir' || event === 'unlinkDir' || DOCS_SOURCE_FILES.has(path.basename(filePath))) {
        console.log(`${event}: ${path.relative(rootDir, filePath)}`);
        try {
          cleanupDocs();
          syncAllDocs();
        } catch (error) {
          // Keep watching: the next edit may fix the problem.
          console.error('Sync failed:', error);
        }
      }
    })
    .on('error', (error: unknown) => {
      console.error('Watch error:', error);
    });

  console.log(`Watching ${commandsDir} for embedded docs and .command files`);

  process.on('SIGINT', () => {
    void watcher.close().then(() => process.exit(0));
  });
}

/**
 * Clean up generated docs (remove files that no longer have embedded sources)
 */
function cleanupDocs(): void {
  if (!fs.existsSync(docsOutputDir)) {
    return;
  }

  const commandDocs = findCommandDocs();
  const expectedFiles = new Set(commandDocs.map(doc => path.basename(doc.outputPath)));
  // Keep manually-authored index file or any other non-generated files
  const doNotDelete = new Set<string>(["index.mdx", "index.md"]);
  
  const existingFiles = fs.readdirSync(docsOutputDir)
    .filter(file => file.endsWith('.mdx') || file.endsWith('.md'));

  for (const file of existingFiles) {
    if (!expectedFiles.has(file) && !doNotDelete.has(file)) {
      const filePath = path.join(docsOutputDir, file);
      fs.unlinkSync(filePath);
      console.log(`Removed orphaned doc: ${file}`);
    }
  }
}

// CLI interface
const command = process.argv[2] ?? 'sync';

try {
  switch (command) {
    case 'watch':
      watchDocs();
      break;
    case 'clean':
      cleanupDocs();
      console.log('Cleaned up orphaned docs');
      break;
    case 'sync':
      cleanupDocs();
      syncAllDocs();
      break;
    default:
      throw new Error(`Unknown command "${command}"; expected sync, watch, or clean`);
  }
} catch (error) {
  console.error(error instanceof Error ? error.message : error);
  process.exitCode = 1;
}
