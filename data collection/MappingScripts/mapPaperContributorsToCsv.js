#!/usr/bin/env node

const fs = require('fs/promises');
const path = require('path');

function parseArgs(argv) {
  const args = {
    input: path.join(__dirname, '../PureJSONs/researchOutput.JSON'),
    output: path.join(__dirname, '../CsvForDB/paperContributors.csv'),
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

function buildPaperContributorRows(papersJson) {
  const rows = [['paperUUID', 'expertUUID', 'role', 'name', 'lastname']];
  const papers = Array.isArray(papersJson?.items) ? papersJson.items : [];

  for (const paper of papers) {
    const contributors = Array.isArray(paper?.contributors) ? paper.contributors : [];
    for (const contributor of contributors) {
      if (contributor?.typeDiscriminator !== 'InternalContributorAssociation') {
        continue;
      }
      rows.push([
        paper.uuid ?? '',
        contributor.person?.uuid ?? '',
        contributor.role?.term?.en_GB ?? '',
        contributor.name?.firstName ?? '',
        contributor.name?.lastName ?? '',
      ]);
    }
  }

  return rows;
}

async function run() {
  const args = parseArgs(process.argv.slice(2));
  if (args.help) {
    console.log('Usage: node mapPaperContributorsToCsv.js [--input researchOutput.JSON] [--output paperContributors.csv]');
    return;
  }

  const inputPath = path.resolve(args.input);
  const outputPath = path.resolve(args.output);
  const papersJson = JSON.parse(await fs.readFile(inputPath, 'utf8'));
  const rows = buildPaperContributorRows(papersJson);
  const csv = rows.map((row) => row.map(csvEscape).join(',')).join('\n');

  await fs.writeFile(outputPath, `${csv}\n`, 'utf8');
  console.log(`Created ${outputPath} with ${rows.length - 1} rows.`);
}

run().catch((error) => {
  console.error(error.message);
  process.exit(1);
});
