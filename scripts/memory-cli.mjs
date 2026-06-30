import { promises as fs } from 'node:fs';
import path from 'node:path';
import process from 'node:process';
import { pathToFileURL } from 'node:url';

const DEFAULT_ROOTS = ['memory', 'basic-memory'];
const DEFAULT_OUTPUT_DIR = path.join('memory', '_system');
const DEFAULT_LINK_WEIGHT = 0.35;
const DEFAULT_IMPORTANCE = 0.5;
const NOTE_EXTENSIONS = new Set(['.md', '.markdown']);
const GENERATED_NOTE_NAMES = new Set(['Memory Dashboard.generated.md']);

export async function discoverNotes(roots, cwd = process.cwd()) {
  const files = [];
  for (const root of roots) {
    const absoluteRoot = path.resolve(cwd, root);
    if (!(await pathExists(absoluteRoot))) {
      continue;
    }
    const entries = await walkDirectory(absoluteRoot);
    for (const entry of entries) {
      if (
        NOTE_EXTENSIONS.has(path.extname(entry).toLowerCase()) &&
        !GENERATED_NOTE_NAMES.has(path.basename(entry))
      ) {
        files.push(entry);
      }
    }
  }
  files.sort();
  return files;
}

export async function parseNoteFile(filePath, cwd = process.cwd()) {
  const raw = await fs.readFile(filePath, 'utf8');
  const { frontmatter, body } = extractFrontmatter(raw);
  const parsedFrontmatter = parseSimpleFrontmatter(frontmatter);
  const relativePath = normalizePath(path.relative(cwd, filePath));
  const noteId = relativePath.replace(/\.(md|markdown)$/i, '');
  const fileStem = path.basename(filePath, path.extname(filePath));
  const title =
    parsedFrontmatter.title ||
    parsedFrontmatter.name ||
    extractHeading(body) ||
    fileStem;
  const weightedLinks = parseWeightedLinks(body);
  const wikilinks = parseWikiLinks(body);

  return {
    id: noteId,
    filePath,
    relativePath,
    fileStem,
    title,
    type: parsedFrontmatter.type || 'note',
    status: parsedFrontmatter.status || 'active',
    tags: normalizeStringArray(parsedFrontmatter.tags),
    aliases: normalizeStringArray(parsedFrontmatter.aliases),
    importance: normalizeImportance(parsedFrontmatter.importance),
    created:
      parsedFrontmatter.created || parsedFrontmatter.created_at || undefined,
    updated:
      parsedFrontmatter.updated || parsedFrontmatter.updated_at || undefined,
    frontmatter: parsedFrontmatter,
    body,
    weightedLinks,
    wikilinks,
    isGenerated: GENERATED_NOTE_NAMES.has(path.basename(filePath)),
    raw,
  };
}

export async function buildMemoryIndex({
  roots = DEFAULT_ROOTS,
  cwd = process.cwd(),
}) {
  const files = await discoverNotes(roots, cwd);
  const notes = await Promise.all(files.map((file) => parseNoteFile(file, cwd)));
  const lookup = buildLookup(notes);
  const { edges, unresolvedLinks, backlinks } = buildGraph(notes, lookup);
  const catalog = buildCatalog(notes, backlinks, edges);

  return {
    generatedAt: new Date().toISOString(),
    roots: roots.map((root) => normalizePath(root)),
    noteCount: notes.length,
    edgeCount: edges.length,
    notes: catalog,
    edges,
    unresolvedLinks,
  };
}

export function searchIndex(index, query, limit = 10) {
  const tokens = tokenize(query);
  if (tokens.length === 0) {
    return [];
  }

  return [...index.notes]
    .map((note) => ({
      note,
      score: searchScore(note, tokens),
    }))
    .filter((entry) => entry.score > 0)
    .sort((left, right) => {
      if (right.score !== left.score) {
        return right.score - left.score;
      }
      return right.note.linkScore - left.note.linkScore;
    })
    .slice(0, limit);
}

export function findRelated(index, noteSelector, limit = 10) {
  const note = resolveNote(index.notes, noteSelector);
  if (!note) {
    throw new Error(`Unknown note: ${noteSelector}`);
  }

  const scores = new Map();
  for (const edge of index.edges) {
    if (edge.sourceId === note.id) {
      const current = scores.get(edge.targetId) ?? 0;
      scores.set(edge.targetId, current + edge.weight * 2);
    }
    if (edge.targetId === note.id) {
      const current = scores.get(edge.sourceId) ?? 0;
      scores.set(edge.sourceId, current + edge.weight * 1.5);
    }
  }

  const noteTagSet = new Set(note.tags.map((tag) => tag.toLowerCase()));
  for (const candidate of index.notes) {
    if (candidate.id === note.id) {
      continue;
    }
    const overlap = candidate.tags.filter((tag) =>
      noteTagSet.has(tag.toLowerCase()),
    ).length;
    if (overlap > 0) {
      scores.set(candidate.id, (scores.get(candidate.id) ?? 0) + overlap * 0.4);
    }
  }

  return [...scores.entries()]
    .map(([candidateId, score]) => ({
      note: index.notes.find((candidate) => candidate.id === candidateId),
      score,
    }))
    .filter((entry) => entry.note)
    .sort((left, right) => {
      if (right.score !== left.score) {
        return right.score - left.score;
      }
      return right.note.importance - left.note.importance;
    })
    .slice(0, limit);
}

export async function writeMemoryArtifacts(
  index,
  {
    outputDir = DEFAULT_OUTPUT_DIR,
    cwd = process.cwd(),
  } = {},
) {
  const absoluteOutputDir = path.resolve(cwd, outputDir);
  await fs.mkdir(absoluteOutputDir, { recursive: true });

  const files = [
    {
      name: 'memory-index.json',
      content: JSON.stringify(index, null, 2),
    },
    {
      name: 'memory-graph.json',
      content: JSON.stringify(
        {
          generatedAt: index.generatedAt,
          noteCount: index.noteCount,
          edgeCount: index.edgeCount,
          edges: index.edges,
          unresolvedLinks: index.unresolvedLinks,
        },
        null,
        2,
      ),
    },
    {
      name: 'Memory Dashboard.generated.md',
      content: renderDashboard(index),
    },
  ];

  for (const file of files) {
    await fs.writeFile(path.join(absoluteOutputDir, file.name), file.content);
  }
}

export async function verifyMemoryArtifacts(
  {
    roots = DEFAULT_ROOTS,
    outputDir = DEFAULT_OUTPUT_DIR,
    cwd = process.cwd(),
  } = {},
) {
  const freshIndex = await buildMemoryIndex({ roots, cwd });
  const expectedDashboard = renderDashboard(freshIndex);
  const expectedIndexObject = freshIndex;
  const expectedGraphObject = {
    generatedAt: freshIndex.generatedAt,
    noteCount: freshIndex.noteCount,
    edgeCount: freshIndex.edgeCount,
    edges: freshIndex.edges,
    unresolvedLinks: freshIndex.unresolvedLinks,
  };
  const expectedIndexJson = JSON.stringify(expectedIndexObject, null, 2);
  const expectedGraphJson = JSON.stringify(
    {
      generatedAt: freshIndex.generatedAt,
      noteCount: freshIndex.noteCount,
      edgeCount: freshIndex.edgeCount,
      edges: freshIndex.edges,
      unresolvedLinks: freshIndex.unresolvedLinks,
    },
    null,
    2,
  );

  const absoluteOutputDir = path.resolve(cwd, outputDir);
  const files = [
    ['Memory Dashboard.generated.md', expectedDashboard],
    ['memory-index.json', expectedIndexJson],
    ['memory-graph.json', expectedGraphJson],
  ];

  const mismatches = [];
  for (const [fileName, expectedContent] of files) {
    const targetPath = path.join(absoluteOutputDir, fileName);
    if (!(await pathExists(targetPath))) {
      mismatches.push(`${normalizePath(path.relative(cwd, targetPath))} is missing`);
      continue;
    }

    const actualContent = await fs.readFile(targetPath, 'utf8');
    if (
      fileName.endsWith('.json')
        ? !jsonMatchesIgnoringGeneratedAt(
            actualContent,
            fileName === 'memory-index.json'
                ? expectedIndexObject
                : expectedGraphObject,
          )
        : actualContent !== expectedContent
    ) {
      mismatches.push(
        `${normalizePath(path.relative(cwd, targetPath))} is stale`,
      );
    }
  }

  return {
    ok: mismatches.length === 0,
    mismatches,
  };
}

function jsonMatchesIgnoringGeneratedAt(actualContent, expectedObject) {
  let actualObject;
  try {
    actualObject = JSON.parse(actualContent);
  } catch {
    return false;
  }

  const actualNormalized = structuredClone(actualObject);
  const expectedNormalized = structuredClone(expectedObject);
  if (actualNormalized && typeof actualNormalized === 'object') {
    delete actualNormalized.generatedAt;
  }
  if (expectedNormalized && typeof expectedNormalized === 'object') {
    delete expectedNormalized.generatedAt;
  }

  return JSON.stringify(actualNormalized) === JSON.stringify(expectedNormalized);
}

export async function captureNote(
  options,
  cwd = process.cwd(),
) {
  const {
    title,
    type = 'session',
    importance = DEFAULT_IMPORTANCE,
    dir = path.join('memory', 'sessions'),
    tags = [],
    summary = '',
    body = '',
    links = [],
    status = 'active',
  } = options;

  if (!title || title.trim() === '') {
    throw new Error('The capture command requires --title.');
  }

  const now = new Date().toISOString().slice(0, 10);
  const slug = slugify(title);
  const filePath = path.resolve(cwd, dir, `${slug}.md`);
  await fs.mkdir(path.dirname(filePath), { recursive: true });

  const rendered = renderNoteTemplate({
    title: title.trim(),
    type,
    importance: normalizeImportance(importance),
    status,
    created: now,
    updated: now,
    tags: typeof tags === 'string' ? splitCsv(tags) : tags,
    summary,
    body,
    links: links.map(parseCaptureLink),
  });

  await fs.writeFile(filePath, rendered);
  return filePath;
}

export function renderNoteTemplate({
  title,
  type,
  importance,
  status,
  created,
  updated,
  tags,
  summary,
  body,
  links,
}) {
  const lines = [
    '---',
    `title: ${title}`,
    `type: ${type}`,
    `importance: ${Number(importance).toFixed(2)}`,
    `status: ${status}`,
    `created: ${created}`,
    `updated: ${updated}`,
    `tags: [${tags.join(', ')}]`,
    '---',
    '',
    `# ${title}`,
    '',
    '## Summary',
    summary.trim() || 'TODO',
    '',
    '## Context',
    body.trim() || 'TODO',
    '',
    '## Weighted links',
  ];

  if (links.length === 0) {
    lines.push(
      '- [[Memory Home]] | weight: 0.40 | relation: index | reason: New notes should stay discoverable from the vault home.',
    );
  } else {
    for (const link of links) {
      lines.push(
        `- [[${link.target}]] | weight: ${Number(link.weight).toFixed(2)} | relation: ${link.relation} | reason: ${link.reason}`,
      );
    }
  }

  lines.push('', '## References', '- TODO');
  return `${lines.join('\n')}\n`;
}

export function renderDashboard(index) {
  const topNotes = [...index.notes]
    .sort((left, right) => right.centrality - left.centrality)
    .slice(0, 12);
  const recentNotes = [...index.notes]
    .filter((note) => /^\d{4}-\d{2}-\d{2}$/.test(String(note.updated || '')))
    .sort((left, right) => String(right.updated).localeCompare(String(left.updated)))
    .slice(0, 10);
  const unresolved = index.unresolvedLinks.slice(0, 20);
  const orphans = index.notes.filter(
    (note) => note.incomingLinks === 0 && note.outgoingLinks === 0,
  );
  const strongEdges = [...index.edges]
    .sort((left, right) => right.weight - left.weight)
    .slice(0, 15);

  const lines = [
    '---',
    'title: Memory Dashboard',
    'type: system',
    'importance: 1.00',
    'status: active',
    `updated: ${index.generatedAt.slice(0, 10)}`,
    'tags: [memory, dashboard, system]',
    '---',
    '',
    '# Memory Dashboard',
    '',
    'This file is generated by `npm run memory:index`.',
    '',
    '## Vault',
    `- Notes indexed: ${index.noteCount}`,
    `- Weighted and implicit links indexed: ${index.edgeCount}`,
    `- Source roots: ${index.roots.map((root) => `\`${root}\``).join(', ')}`,
    '',
    '## Operating notes',
    '- Open [[Codex Memory Protocol]] before extending the workflow.',
    '- Open [[Memory Home]] for the human-oriented entrypoint.',
    '- Run `npm run memory:index` after editing notes by hand.',
    '- Use `npm run memory:search -- "<query>"` to find context quickly.',
    '',
    '## Hubs',
    ...topNotes.map(
      (note) =>
        `- [[${note.title}]] | centrality: ${note.centrality.toFixed(2)} | importance: ${note.importance.toFixed(2)} | path: \`${note.relativePath}\``,
    ),
    '',
    '## Strong links',
    ...strongEdges.map(
      (edge) =>
        `- [[${edge.sourceTitle}]] -> [[${edge.targetTitle}]] | weight: ${edge.weight.toFixed(2)} | relation: ${edge.relation}`,
    ),
    '',
    '## Recently updated',
    ...recentNotes.map(
      (note) =>
        `- [[${note.title}]] | updated: ${note.updated} | tags: ${note.tags.join(', ') || '-'}`,
    ),
    '',
    '## Orphans',
    ...(orphans.length === 0
      ? ['- None']
      : orphans.map((note) => `- [[${note.title}]] | path: \`${note.relativePath}\``)),
    '',
    '## Unresolved links',
    ...(unresolved.length === 0
      ? ['- None']
      : unresolved.map(
          (link) =>
            `- [[${link.target}]] referenced from [[${link.sourceTitle}]] | relation: ${link.relation}`,
        )),
    '',
  ];

  return `${lines.join('\n')}\n`;
}

export function renderDoctorReport(index) {
  const lines = [
    `Indexed ${index.noteCount} notes and ${index.edgeCount} links.`,
    `Unresolved links: ${index.unresolvedLinks.length}.`,
  ];

  if (index.unresolvedLinks.length > 0) {
    for (const item of index.unresolvedLinks.slice(0, 20)) {
      lines.push(
        `- ${item.sourceTitle} -> [[${item.target}]] (${item.relation})`,
      );
    }
  }

  return lines.join('\n');
}

function buildLookup(notes) {
  const lookup = new Map();
  for (const note of notes) {
    const keys = new Set([
      normalizeLookupKey(note.id),
      normalizeLookupKey(note.title),
      normalizeLookupKey(note.fileStem),
      normalizeLookupKey(note.relativePath.replace(/\.(md|markdown)$/i, '')),
    ]);
    for (const alias of note.aliases) {
      keys.add(normalizeLookupKey(alias));
    }
    for (const key of keys) {
      if (key) {
        lookup.set(key, note);
      }
    }
  }
  return lookup;
}

function buildGraph(notes, lookup) {
  const edges = [];
  const unresolvedLinks = [];
  const backlinks = new Map();

  for (const note of notes) {
    if (note.isGenerated) {
      continue;
    }

    for (const explicitLink of note.weightedLinks) {
      const targetNote = lookup.get(normalizeLookupKey(explicitLink.target));
      if (!targetNote) {
        unresolvedLinks.push({
          sourceId: note.id,
          sourceTitle: note.title,
          target: explicitLink.target,
          relation: explicitLink.relation,
        });
        continue;
      }

      const edge = createEdge(note, targetNote, explicitLink.weight, {
        relation: explicitLink.relation,
        reason: explicitLink.reason,
        explicit: true,
      });
      edges.push(edge);
      addBacklink(backlinks, targetNote.id, edge);
    }

    const explicitTargets = new Set(
      note.weightedLinks.map((link) => normalizeLookupKey(link.target)),
    );
    for (const implicitLink of note.wikilinks) {
      const normalizedTarget = normalizeLookupKey(implicitLink.target);
      if (explicitTargets.has(normalizedTarget)) {
        continue;
      }
      const targetNote = lookup.get(normalizeLookupKey(implicitLink.target));
      if (!targetNote) {
        unresolvedLinks.push({
          sourceId: note.id,
          sourceTitle: note.title,
          target: implicitLink.target,
          relation: 'reference',
        });
        continue;
      }

      const edge = createEdge(note, targetNote, DEFAULT_LINK_WEIGHT, {
        relation: 'reference',
        reason: 'Implicit wiki link',
        explicit: false,
      });
      edges.push(edge);
      addBacklink(backlinks, targetNote.id, edge);
    }
  }

  return { edges, unresolvedLinks, backlinks };
}

function buildCatalog(notes, backlinks, edges) {
  return notes.map((note) => {
    const incoming = backlinks.get(note.id) ?? [];
    const outgoing = edges.filter((edge) => edge.sourceId === note.id);
    const inboundWeight = incoming.reduce((sum, edge) => sum + edge.weight, 0);
    const outboundWeight = outgoing.reduce((sum, edge) => sum + edge.weight, 0);
    const centrality = note.importance * 2 + inboundWeight + outboundWeight * 0.75;

    return {
      id: note.id,
      title: note.title,
      relativePath: note.relativePath,
      type: note.type,
      status: note.status,
      tags: note.tags,
      aliases: note.aliases,
      importance: note.importance,
      created: note.created,
      updated: note.updated,
      incomingLinks: incoming.length,
      outgoingLinks: outgoing.length,
      inboundWeight: round2(inboundWeight),
      outboundWeight: round2(outboundWeight),
      centrality: round2(centrality),
      linkScore: round2(inboundWeight + outboundWeight),
      excerpt: makeExcerpt(note.body),
      searchableText: [
        note.title,
        note.type,
        note.tags.join(' '),
        note.aliases.join(' '),
        note.body,
      ]
        .join(' ')
        .toLowerCase(),
    };
  });
}

function createEdge(source, target, weight, metadata) {
  return {
    sourceId: source.id,
    sourceTitle: source.title,
    targetId: target.id,
    targetTitle: target.title,
    weight: round2(weight),
    relation: metadata.relation || 'reference',
    reason: metadata.reason || '',
    explicit: Boolean(metadata.explicit),
  };
}

function addBacklink(backlinks, targetId, edge) {
  const current = backlinks.get(targetId) ?? [];
  current.push(edge);
  backlinks.set(targetId, current);
}

function resolveNote(notes, selector) {
  const normalized = normalizeLookupKey(selector);
  return notes.find((note) => {
    if (normalizeLookupKey(note.id) === normalized) {
      return true;
    }
    if (normalizeLookupKey(note.title) === normalized) {
      return true;
    }
    return note.aliases.some((alias) => normalizeLookupKey(alias) === normalized);
  });
}

function searchScore(note, tokens) {
  let score = note.importance;
  for (const token of tokens) {
    if (note.title.toLowerCase().includes(token)) {
      score += 8;
    }
    if (note.tags.some((tag) => tag.toLowerCase().includes(token))) {
      score += 5;
    }
    if (note.aliases.some((alias) => alias.toLowerCase().includes(token))) {
      score += 4;
    }
    const occurrences = countOccurrences(note.searchableText, token);
    score += Math.min(occurrences, 8) * 0.6;
  }
  score += note.centrality * 0.2;
  return round2(score);
}

function extractFrontmatter(raw) {
  if (!raw.startsWith('---\n') && !raw.startsWith('---\r\n')) {
    return { frontmatter: '', body: raw };
  }

  const normalized = raw.replace(/\r\n/g, '\n');
  const endMarker = '\n---\n';
  const endIndex = normalized.indexOf(endMarker, 4);
  if (endIndex === -1) {
    return { frontmatter: '', body: raw };
  }

  return {
    frontmatter: normalized.slice(4, endIndex),
    body: normalized.slice(endIndex + endMarker.length),
  };
}

function parseSimpleFrontmatter(frontmatter) {
  if (!frontmatter) {
    return {};
  }

  const result = {};
  let currentArrayKey = null;
  for (const rawLine of frontmatter.split('\n')) {
    const line = rawLine.trimEnd();
    if (line.trim() === '') {
      continue;
    }

    if (currentArrayKey && /^\s*-\s+/.test(rawLine)) {
      result[currentArrayKey].push(parseScalar(rawLine.replace(/^\s*-\s+/, '')));
      continue;
    }

    currentArrayKey = null;
    const match = rawLine.match(/^([A-Za-z0-9_-]+):\s*(.*)$/);
    if (!match) {
      continue;
    }

    const [, key, value] = match;
    if (value === '') {
      result[key] = [];
      currentArrayKey = key;
      continue;
    }

    if (value.startsWith('[') && value.endsWith(']')) {
      const inner = value.slice(1, -1).trim();
      result[key] = inner === '' ? [] : splitCsv(inner);
      continue;
    }

    result[key] = parseScalar(value);
  }

  return result;
}

function parseScalar(value) {
  const trimmed = value.trim();
  if (/^-?\d+(?:\.\d+)?$/.test(trimmed)) {
    return Number(trimmed);
  }
  if (trimmed === 'true') {
    return true;
  }
  if (trimmed === 'false') {
    return false;
  }
  return trimmed.replace(/^['"]|['"]$/g, '');
}

function parseWeightedLinks(body) {
  const links = [];
  const lines = body.split('\n');
  let inWeightedSection = false;

  for (const line of lines) {
    const headingMatch = line.match(/^##+\s+(.*)$/);
    if (headingMatch) {
      const heading = headingMatch[1].trim().toLowerCase();
      inWeightedSection = heading === 'weighted links';
      continue;
    }

    if (!inWeightedSection) {
      continue;
    }

    if (!line.trim().startsWith('- ')) {
      continue;
    }

    const match = line.match(
      /^-\s+\[\[([^[\]|]+)(?:\|[^[\]]+)?\]\]\s*\|\s*weight:\s*([0-9.]+)\s*\|\s*relation:\s*([^|]+?)\s*\|\s*reason:\s*(.+)\s*$/i,
    );
    if (!match) {
      continue;
    }

    links.push({
      target: match[1].trim(),
      weight: normalizeImportance(Number(match[2])),
      relation: match[3].trim(),
      reason: match[4].trim(),
    });
  }

  return links;
}

function parseWikiLinks(body) {
  const links = [];
  const sanitizedBody = stripCode(body);
  const regex = /\[\[([^[\]]+)\]\]/g;
  for (const match of sanitizedBody.matchAll(regex)) {
    const rawTarget = match[1].trim();
    if (rawTarget === '') {
      continue;
    }
    const [target] = rawTarget.split('|');
    links.push({ target: target.trim() });
  }
  return links;
}

function stripCode(body) {
  return body
    .replace(/```[\s\S]*?```/g, '')
    .replace(/`[^`\n]+`/g, '');
}

function extractHeading(body) {
  const match = body.match(/^#\s+(.+)$/m);
  return match ? match[1].trim() : null;
}

function normalizeStringArray(value) {
  if (Array.isArray(value)) {
    return value.map((entry) => String(entry).trim()).filter(Boolean);
  }
  if (typeof value === 'string') {
    return splitCsv(value);
  }
  return [];
}

function normalizeImportance(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) {
    return DEFAULT_IMPORTANCE;
  }
  return Math.min(1, Math.max(0, numeric));
}

function normalizeLookupKey(value) {
  return String(value)
    .trim()
    .toLowerCase()
    .replace(/\\/g, '/')
    .replace(/\.(md|markdown)$/i, '');
}

function normalizePath(value) {
  return value.replace(/\\/g, '/');
}

function splitCsv(value) {
  return value
    .split(',')
    .map((entry) => entry.trim())
    .filter(Boolean);
}

function tokenize(value) {
  return String(value)
    .toLowerCase()
    .split(/[^a-z0-9/_-]+/)
    .map((token) => token.trim())
    .filter(Boolean);
}

function countOccurrences(haystack, needle) {
  if (!haystack.includes(needle)) {
    return 0;
  }
  let count = 0;
  let index = 0;
  while ((index = haystack.indexOf(needle, index)) !== -1) {
    count += 1;
    index += needle.length;
  }
  return count;
}

function makeExcerpt(body, maxLength = 180) {
  const normalized = body
    .replace(/\r\n/g, '\n')
    .replace(/^#+\s+/gm, '')
    .replace(/\[\[([^[\]]+)\]\]/g, '$1')
    .replace(/\s+/g, ' ')
    .trim();
  if (normalized.length <= maxLength) {
    return normalized;
  }
  return `${normalized.slice(0, maxLength - 3)}...`;
}

function round2(value) {
  return Math.round(value * 100) / 100;
}

function parseCaptureLink(rawLink) {
  const parts = String(rawLink).split('|').map((part) => part.trim());
  return {
    target: parts[0] || 'Memory Home',
    weight: normalizeImportance(parts[1] || DEFAULT_IMPORTANCE),
    relation: parts[2] || 'related_to',
    reason: parts[3] || 'Captured from CLI.',
  };
}

function slugify(value) {
  return String(value)
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .replace(/-{2,}/g, '-');
}

async function walkDirectory(directory) {
  const entries = await fs.readdir(directory, { withFileTypes: true });
  const files = [];
  for (const entry of entries) {
    const absolutePath = path.join(directory, entry.name);
    if (entry.isDirectory()) {
      files.push(...(await walkDirectory(absolutePath)));
    } else if (entry.isFile()) {
      files.push(absolutePath);
    }
  }
  return files;
}

async function pathExists(targetPath) {
  try {
    await fs.access(targetPath);
    return true;
  } catch {
    return false;
  }
}

async function main(argv = process.argv.slice(2)) {
  const [command, ...rest] = argv;
  const args = parseCliArgs(rest);

  switch (command) {
    case 'index': {
      const roots = args.roots ? splitCsv(args.roots) : DEFAULT_ROOTS;
      const index = await buildMemoryIndex({ roots });
      await writeMemoryArtifacts(index, {
        outputDir: args['output-dir'] || DEFAULT_OUTPUT_DIR,
      });
      console.log(
        `Indexed ${index.noteCount} notes and wrote artifacts to ${args['output-dir'] || DEFAULT_OUTPUT_DIR}.`,
      );
      break;
    }
    case 'search': {
      const query = args._.join(' ').trim();
      if (query === '') {
        throw new Error('Provide a query, for example: npm run memory:search -- payment');
      }
      const index = await buildMemoryIndex({
        roots: args.roots ? splitCsv(args.roots) : DEFAULT_ROOTS,
      });
      const results = searchIndex(index, query, Number(args.limit || 10));
      if (results.length === 0) {
        console.log(`No notes matched "${query}".`);
        break;
      }
      for (const [position, result] of results.entries()) {
        console.log(
          `${position + 1}. ${result.note.title} | score ${result.score.toFixed(2)} | ${result.note.relativePath}`,
        );
        console.log(`   ${result.note.excerpt}`);
      }
      break;
    }
    case 'related': {
      const selector = args._.join(' ').trim();
      if (selector === '') {
        throw new Error(
          'Provide a note title or path stem, for example: npm run memory:related -- "Memory Home"',
        );
      }
      const index = await buildMemoryIndex({
        roots: args.roots ? splitCsv(args.roots) : DEFAULT_ROOTS,
      });
      const results = findRelated(index, selector, Number(args.limit || 10));
      for (const [position, result] of results.entries()) {
        console.log(
          `${position + 1}. ${result.note.title} | score ${result.score.toFixed(2)} | ${result.note.relativePath}`,
        );
      }
      break;
    }
    case 'capture': {
      const links = []
        .concat(args.link || [])
        .concat(args.links || [])
        .filter(Boolean);
      const filePath = await captureNote({
        title: args.title,
        type: args.type,
        importance: args.importance,
        dir: args.dir,
        tags: args.tags || '',
        summary: args.summary || '',
        body: args.body || '',
        links,
        status: args.status || 'active',
      });
      console.log(`Created ${normalizePath(path.relative(process.cwd(), filePath))}`);
      break;
    }
    case 'doctor': {
      const index = await buildMemoryIndex({
        roots: args.roots ? splitCsv(args.roots) : DEFAULT_ROOTS,
      });
      console.log(renderDoctorReport(index));
      break;
    }
    case 'verify': {
      const result = await verifyMemoryArtifacts({
        roots: args.roots ? splitCsv(args.roots) : DEFAULT_ROOTS,
        outputDir: args['output-dir'] || DEFAULT_OUTPUT_DIR,
      });
      if (!result.ok) {
        console.error('Memory artifacts are not up to date.');
        for (const mismatch of result.mismatches) {
          console.error(`- ${mismatch}`);
        }
        console.error('Run `npm run memory:index` to refresh them.');
        process.exitCode = 1;
        break;
      }
      console.log('Memory artifacts are up to date.');
      break;
    }
    default:
      console.log(
        [
          'Memory CLI',
          '',
          'Commands:',
          '  node scripts/memory-cli.mjs index',
          '  node scripts/memory-cli.mjs search "payment webhook"',
          '  node scripts/memory-cli.mjs related "Memory Home"',
          '  node scripts/memory-cli.mjs capture --title "Session" --summary "..."',
          '  node scripts/memory-cli.mjs doctor',
          '  node scripts/memory-cli.mjs verify',
        ].join('\n'),
      );
  }
}

function parseCliArgs(argv) {
  const args = { _: [] };
  for (let index = 0; index < argv.length; index += 1) {
    const current = argv[index];
    if (!current.startsWith('--')) {
      args._.push(current);
      continue;
    }

    const key = current.slice(2);
    const next = argv[index + 1];
    if (next && !next.startsWith('--')) {
      if (args[key] === undefined) {
        args[key] = next;
      } else if (Array.isArray(args[key])) {
        args[key].push(next);
      } else {
        args[key] = [args[key], next];
      }
      index += 1;
      continue;
    }
    args[key] = true;
  }
  return args;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  main().catch((error) => {
    console.error(error.message);
    process.exitCode = 1;
  });
}
