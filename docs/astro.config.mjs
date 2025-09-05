// @ts-check
import { defineConfig, passthroughImageService } from "astro/config";
import starlight from "@astrojs/starlight";

import tailwindcss from "@tailwindcss/vite";
import starlightSiteGraph from "starlight-site-graph";

// https://astro.build/config
export default defineConfig({
  image: {
    service: passthroughImageService(),
  },

  site: "https://kilm.aristovnik.me",

  integrations: [
    starlight({
      // plugins: [starlightSiteGraph()],
      title: "KiLM",
      customCss: [
        // Path to your custom CSS file (relative to src)
        "./src/styles/global.css",
      ],
      components: {
        // Override the default Footer component with our custom one
        Footer: "./src/components/Footer.astro",
      },
      social: [
        {
          icon: "github",
          label: "GitHub",
          href: "https://github.com/barisgit/kilm",
        },
      ],
      sidebar: [
        {
          label: "Guides",
          items: [
            { label: "Getting Started", link: "/guides/getting-started/" },
            { label: "Installation", link: "/guides/installation/" },
            { label: "Configuration", link: "/guides/configuration/" },
            {
              label: "Custom Descriptions",
              link: "/guides/custom-descriptions/",
            },
            { label: "Automatic Updates", link: "/guides/automatic-updates/" },
            { label: "Troubleshooting", link: "/guides/troubleshooting/" },
          ],
        },
        {
          label: "Command Reference",
          items: [
            { label: "Overview", link: "/reference/cli/" },
            { label: "init", link: "/reference/cli/init/" },
            { label: "add-3d", link: "/reference/cli/add-3d/" },
            { label: "config", link: "/reference/cli/config/" },
            { label: "setup", link: "/reference/cli/setup/" },
            { label: "pin", link: "/reference/cli/pin/" },
            { label: "unpin", link: "/reference/cli/unpin/" },
            { label: "template", link: "/reference/cli/template/" },
            { label: "list", link: "/reference/cli/list/" },
            { label: "status", link: "/reference/cli/status/" },
            { label: "sync", link: "/reference/cli/sync/" },
            { label: "update", link: "/reference/cli/update/" },
            { label: "add-hook", link: "/reference/cli/add-hook/" },
          ],
        },
        {
          label: "Community",
          items: [
            { label: "Development Setup", link: "/community/development/" },
            { label: "Contributing", link: "/community/contributing/" },
            { label: "License", link: "/community/license/" },
          ],
        },
      ],
    }),
  ],
  vite: {
    plugins: [tailwindcss()],
  },
});
