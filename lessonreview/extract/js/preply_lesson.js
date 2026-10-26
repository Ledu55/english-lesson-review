// Runs on preply.com/edu/lesson-insights/<lessonId>. Expands the full grammar and vocabulary lists
// (they open inline) and returns the page text, one line per entry.
async () => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const text = () => (document.querySelector('main') || document.body).innerText;
  const ready = () => /(You said|Você disse|Talk time|Tempo de conversação|Topic of the day|Tema do dia)/i.test(text());
  for (let i = 0; i < 40 && !ready(); i++) await sleep(500);
  if (/404|page not found|página não encontrada/i.test(text().slice(0, 400))) return { error: 'not_found' };
  if (!ready()) return { error: 'no_insights' };

  for (const re of [/^(See all grammar feedback|Ver todo o feedback de gramática)$/i,
                    /^(See all vocabulary|Ver todo o vocabulário)$/i]) {
    const label = [...document.querySelectorAll('body *')]
      .find(e => e.children.length === 0 && re.test((e.innerText || '').trim()));
    const button = label && label.closest('a,button,[role=button],[role=link]');
    if (button) { button.click(); await sleep(2500); }
  }
  return { lines: text().split('\n').map(s => s.trim()).filter(Boolean) };
}
