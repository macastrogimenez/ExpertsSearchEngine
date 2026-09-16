#!/usr/bin/env node

const fs = require('fs/promises');
const path = require('path');

function parseArgs(argv) {
  const args = {
    input: '../PureJSONs/persons.JSON',
    output: '../CsvForDB/person.csv',
  };

  for (let index = 0; index < argv.length; index += 1) {
    const current = argv[index];
    if (current === '--input' && argv[index + 1]) {
      args.input = argv[index + 1];
      index += 1;
      continue;
    }
    if (current === '--output' && argv[index + 1]) {
      args.output = argv[index + 1];
      index += 1;
      continue;
    }
    if (current === '--help' || current === '-h') {
      args.help = true;
    }
  }

  return args;
}

function csvEscape(value) {
  const text = value === undefined || value === null ? '' : String(value);
  if (text.includes(',') || text.includes('"') || text.includes('\n') || text.includes('\r')) {
    return `"${text.replace(/"/g, '""')}"`;
  }
  return text;
}

function getFirstAssociation(person) {
  if (!Array.isArray(person?.staffOrganizationAssociations)) {
    return undefined;
  }
  return person.staffOrganizationAssociations[0];
}

function getFirstEmailValue(association) {
  if (!Array.isArray(association?.emails)) {
    return '';
  }
  return association.emails[0]?.value ?? '';
}

async function readJsonFile(filePath) {
  const content = await fs.readFile(filePath, 'utf8');
  return JSON.parse(content);
}

function buildPersonsCsvRows(personsJson) {
  const rows = [['uuid','orcid', 'firstName', 'lastName', 'email', 'jobTitle']];
  const items = Array.isArray(personsJson?.items) ? personsJson.items : [];

  for (const person of items) {
    const firstAssociation = getFirstAssociation(person);
    const jobTitleEnGb = firstAssociation?.jobTitle?.term?.en_GB ?? '';

    rows.push([
      person?.uuid ?? '',
      person?.orcid ?? '',
      (person?.name?.firstName ?? '').trim(),
      (person?.name?.lastName ?? '').trim(),
      getFirstEmailValue(firstAssociation),
      jobTitleEnGb,
    ]);
  }

  return rows;
}

async function writeCsv(filePath, rows) {
  const csv = rows
    .map((row) => row.map((cell) => csvEscape(cell)).join(','))
    .join('\n');
  await fs.writeFile(filePath, `${csv}\n`, 'utf8');
}

async function run() {
  const args = parseArgs(process.argv.slice(2));

  if (args.help) {
    console.log('Usage: node mapPersonsToCsv.js [--input persons.JSON] [--output person.csv]');
    process.exit(0);
  }

  const inputPath = path.resolve(process.cwd(), args.input);
  const outputPath = path.resolve(process.cwd(), args.output);

  const personsJson = await readJsonFile(inputPath);
  const personRows = buildPersonsCsvRows(personsJson);

  await writeCsv(outputPath, personRows);

  const personCount = Math.max(0, personRows.length - 1);
  console.log(`Created ${args.output} with ${personCount} rows.`);
}

run().catch((error) => {
  console.error(error.message);
  process.exit(1);
});
