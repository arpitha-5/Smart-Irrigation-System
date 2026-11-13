// Verification script for the 5-language translation JSON files
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const localesDir = path.join(__dirname, 'src', 'locales');

const languages = ['en', 'te', 'hi', 'ta', 'kn'];
const data = {};

for (const lang of languages) {
  const filePath = path.join(localesDir, `${lang}.json`);
  if (!fs.existsSync(filePath)) {
    console.error(`Missing locale file: ${filePath}`);
    process.exit(1);
  }
  data[lang] = JSON.parse(fs.readFileSync(filePath, 'utf-8'));
}

function getKeys(obj, prefix = '') {
  let keys = [];
  for (const [k, v] of Object.entries(obj)) {
    const full = prefix ? `${prefix}.${k}` : k;
    if (typeof v === 'object' && v !== null) {
      keys = keys.concat(getKeys(v, full));
    } else {
      keys.push(full);
    }
  }
  return keys;
}

const enKeys = getKeys(data.en);
console.log(`English template has ${enKeys.length} translation keys.`);

let allPassed = true;
for (const lang of languages) {
  if (lang === 'en') continue;
  const langKeys = new Set(getKeys(data[lang]));
  const missing = enKeys.filter((k) => !langKeys.has(k));
  if (missing.length > 0) {
    console.error(`[FAIL] ${lang}.json is missing keys:`, missing);
    allPassed = false;
  } else {
    console.log(`[PASS] ${lang}.json contains all ${enKeys.length} required translation keys!`);
  }
}

if (!allPassed) {
  process.exit(1);
} else {
  console.log('\nAll 5 languages (en, te, hi, ta, kn) verified successfully!');
}
