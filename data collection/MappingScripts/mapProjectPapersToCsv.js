#!/usr/bin/env node

const fs = require('fs/promises');
const path = require('path');

function parseArgs(argv) {
  const args = {
    input: path.join(__dirname, '../PureJSONs/projects.JSON'),
    output: path.join(__dirname, '../CsvForDB/projectPapers.csv'),
  };

  for (let i = 0; i < argv.length; i += 1) {
    const current = argv[i];
    if (current === '--input' || current === '--output') {
      const value = argv[i + 1];
      if (!value || value.startsWith('--')) {
        throw new Error(`Missing value for ${current}`);
      }
      args[current.slice(2)] = value;
      i += 1;
    } else if (current === '--help' || current === '-h') {
      args.help = true;
    } else {
      throw new Error(`Unknown argument: ${current}`);
    }
  }

  return args;
}

function csvEscape(value) {
  const text = value === undefined || value === null ? '' : String(value);
  if (/[,"\n\r]/.test(text)) {
    return `"${text.replace(/"/g, '""')}"`;
  }
  return text;
}

function buildProjectPaperRows(projectsJson) {
  const rows = [['projectUUID', 'paperUUID']];
  const projects = Array.isArray(projectsJson?.items) ? projectsJson.items : [];

  for (const project of projects) {
    const researchOutputs = Array.isArray(project?.researchOutputs) ? project.researchOutputs : [];
    for (const entry of researchOutputs) {
      const paperUuid = entry?.researchOutput?.uuid;
      if (!paperUuid) {
        continue;
      }
      rows.push([project.uuid ?? '', paperUuid]);
    }
  }

  return rows;
}

async function run() {
  const args = parseArgs(process.argv.slice(2));
  if (args.help) {
    console.log('Usage: node mapProjectPapersToCsv.js [--input projects.JSON] [--output projectPapers.csv]');
    return;
  }

  const inputPath = path.resolve(args.input);
  const outputPath = path.resolve(args.output);
  const projectsJson = JSON.parse(await fs.readFile(inputPath, 'utf8'));
  const rows = buildProjectPaperRows(projectsJson);
  const csv = rows.map((row) => row.map(csvEscape).join(',')).join('\n');

  await fs.writeFile(outputPath, `${csv}\n`, 'utf8');
  console.log(`Created ${outputPath} with ${rows.length - 1} rows.`);
}

run().catch((error) => {
  console.error(error.message);
  process.exit(1);
});
