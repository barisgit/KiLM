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
        return commandName;
      }
    } catch (error) {
      console.warn(`Failed to read .command file for ${dirName}:`, error);
    }
  }
  
  // Fallback to directory name
  return dirName;
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
  // Check if content already has frontmatter
  const frontmatterMatch = content.match(/^---\n([\s\S]*?)\n---\n([\s\S]*)$/);
  
  if (frontmatterMatch) {
    // Content already has frontmatter, return as-is
    return content;
  }
  
  // No frontmatter, add it
  // Extract title from first heading or use command name
  const titleMatch = content.match(/^# (.+)$/m);
  const title = titleMatch ? titleMatch[1] : commandName;
  
  // Extract description from content or use default
  const descriptionMatch = content.match(/^(.+)$/m);
  const firstLine = descriptionMatch ? descriptionMatch[1].replace(/^# /, '') : '';
  const description = firstLine || `${commandName} command documentation`;

  // Create frontmatter
  const frontmatter = `---
title: ${title}
description: ${description}
sidebar:
  label: ${commandName}
---

`;

  // Remove the first heading since it's now in frontmatter
  const contentWithoutTitle = content.replace(/^# .+$/m, '').trim();
  
  return frontmatter + contentWithoutTitle;
}

/**
 * Sync a single embedded doc to the output directory
 */
function syncDoc(commandDoc: CommandDoc): void {
  try {
    const content = fs.readFileSync(commandDoc.embeddedPath, 'utf-8');
    const processedContent = processEmbeddedDoc(content, commandDoc.commandName);
    
    // Ensure output directory exists
    const outputDir = path.dirname(commandDoc.outputPath);
    if (!fs.existsSync(outputDir)) {
      fs.mkdirSync(outputDir, { recursive: true });
    }

    fs.writeFileSync(commandDoc.outputPath, processedContent);
    console.log(`Synced ${commandDoc.commandName}.mdx`);
  } catch (error) {
    console.error(`Failed to sync ${commandDoc.commandName}:`, error);
  }
}

/**
 * Sync all embedded docs to the output directory
 */
function syncAllDocs(): void {
  console.log('Syncing embedded documentation...');
  
  const commandDocs = findCommandDocs();
  
  if (commandDocs.length === 0) {
    console.warn('No embedded docs found');
    return;
  }

  // Ensure output directory exists
  if (!fs.existsSync(docsOutputDir)) {
    fs.mkdirSync(docsOutputDir, { recursive: true });
  }

  for (const commandDoc of commandDocs) {
    syncDoc(commandDoc);
  }

  console.log(`Synced ${commandDocs.length} embedded docs`);
}

/**
 * Watch embedded docs for changes and sync automatically
 */
function watchDocs(): void {
  console.log('Watching embedded docs for changes...');
  
  const commandDocs = findCommandDocs();
  const watchPaths = commandDocs.map(doc => doc.embeddedPath);
  
  if (watchPaths.length === 0) {
    console.warn('No embedded docs to watch');
    return;
  }

  // Initial sync
  syncAllDocs();

  // Watch for changes
  const watcher = chokidar.watch(watchPaths, {
    persistent: true,
    ignoreInitial: true,
  });

  watcher
    .on('change', (changedPath: string) => {
      const commandDoc = commandDocs.find(doc => doc.embeddedPath === changedPath);
      if (commandDoc) {
        console.log(`${commandDoc.commandName} docs changed, syncing...`);
        syncDoc(commandDoc);
      }
    })
    .on('error', (error: unknown) => {
      console.error('Watch error:', error);
    });

  console.log(`Watching ${watchPaths.length} embedded docs files`);
  
  // Keep the process running
  process.on('SIGINT', () => {
    console.log('\nStopping watch mode...');
    watcher.close();
    process.exit(0);
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
  
  const existingFiles = fs.readdirSync(docsOutputDir)
    .filter(file => file.endsWith('.mdx') || file.endsWith('.md'));

  for (const file of existingFiles) {
    if (!expectedFiles.has(file)) {
      const filePath = path.join(docsOutputDir, file);
      fs.unlinkSync(filePath);
      console.log(`Removed orphaned doc: ${file}`);
    }
  }
}

// CLI interface
const command = process.argv[2];

switch (command) {
  case 'watch':
    watchDocs();
    break;
  case 'clean':
    cleanupDocs();
    console.log('Cleaned up orphaned docs');
    break;
  case 'sync':
  default:
    cleanupDocs();
    syncAllDocs();
    break;
}