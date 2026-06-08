const { PROMPTS } = require('../src/data/prompts');
const { searchPrompts } = require('../src/lib/prompt-search');

describe('Prompt Library Static Data', () => {
  test('contains required prompts', () => {
    const ids = PROMPTS.map(p => p.id);
    expect(ids).toContain('boot-from-cartridge');
    expect(ids).toContain('ask-for-receipt');
    expect(ids).toContain('generate-receipt-from-chat');
    expect(ids).toContain('chatgpt-upload');
    expect(ids).toContain('claude-upload');
    expect(ids).toContain('gemini-upload');
  });

  test('no remote fetch URLs present in prompts', () => {
    PROMPTS.forEach(prompt => {
      // The rules explicitly forbid remote CDNs or arbitrary network fetches in prompt copy payloads
      const content = prompt.content.toLowerCase();
      expect(content).not.toMatch(/http:\/\//);
      expect(content).not.toMatch(/https:\/\//);
    });
  });
});

describe('Prompt Search Logic', () => {
  test('empty query returns all prompts', () => {
    const result = searchPrompts('', PROMPTS);
    expect(result.length).toBe(PROMPTS.length);
  });

  test('whitespace query returns all prompts', () => {
    const result = searchPrompts('   ', PROMPTS);
    expect(result.length).toBe(PROMPTS.length);
  });

  test('searches by title case-insensitive', () => {
    const result = searchPrompts('BOOT', PROMPTS);
    expect(result.length).toBe(1);
    expect(result[0].id).toBe('boot-from-cartridge');
  });

  test('searches by description', () => {
    const result = searchPrompts('best practice', PROMPTS);
    // 3 upload prompts have "Best practice" in description
    expect(result.length).toBe(3);
  });

  test('searches by tag', () => {
    const result = searchPrompts('anthropic', PROMPTS);
    expect(result.length).toBe(1);
    expect(result[0].id).toBe('claude-upload');
  });

  test('returns empty array when no matches', () => {
    const result = searchPrompts('nonexistent-gibberish-string', PROMPTS);
    expect(result.length).toBe(0);
  });
});
