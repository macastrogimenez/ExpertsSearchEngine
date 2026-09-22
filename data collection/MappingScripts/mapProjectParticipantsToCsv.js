#!/usr/bin/env node

const fs = require('fs/promises');
const path = require('path');

function parseArgs(argv) {
  const args = {
    input: path.join(__dirname, '../PureJSONs/projects.JSON'),
    output: path.join(__dirname, '../CsvForDB/projectParticipants.csv'),
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

function buildParticipantRows(projectsJson) {
  const rows = [['ProjectUUID', 'PersonUUID', 'Role']];
  const projects = Array.isArray(projectsJson?.items) ? projectsJson.items : [];

  for (const project of projects) {
    const participants = Array.isArray(project?.participants) ? project.participants : [];
    for (const participant of participants) {
      if (participant?.typeDiscriminator !== 'InternalParticipantAssociation'
          || !participant?.person?.uuid) {
        continue;
      }

      rows.push([
        project.uuid ?? '',
        participant.person.uuid,
        participant.role?.term?.en_GB ?? '',
      ]);
    }
  }

  return rows;
}

async function run() {
  const args = parseArgs(process.argv.slice(2));
  if (args.help) {
    console.log('Usage: node mapProjectParticipantsToCsv.js [--input projects.JSON] [--output projectParticipants.csv]');
    return;
  }

  const inputPath = path.resolve(args.input);
  const outputPath = path.resolve(args.output);
  const projectsJson = JSON.parse(await fs.readFile(inputPath, 'utf8'));
  const rows = buildParticipantRows(projectsJson);
  const csv = rows.map((row) => row.map(csvEscape).join(',')).join('\n');

  await fs.writeFile(outputPath, `${csv}\n`, 'utf8');
  console.log(`Created ${outputPath} with ${rows.length - 1} rows.`);
}

run().catch((error) => {
  console.error(error.message);
  process.exit(1);
});
