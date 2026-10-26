// Runs on www.cambly.com/en/student/progress/past-lesson?lessonV2Id=<id>.
// Opens the FEEDBACK and TRANSCRIPT tabs and returns their text. The learner is told apart from the
// tutor by the avatar image, whose URL contains the user id.
async (userId) => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const leaf = re => [...document.querySelectorAll('body *')]
    .find(e => e.children.length === 0 && re.test((e.innerText || '').trim()));
  const FEEDBACK = /^(FEEDBACK|COMENTÁRIOS|COMENTARIOS)$/i, TRANSCRIPT = /^(TRANSCRIPT|TRANSCRIÇÃO|TRANSCRIPCIÓN)$/i;
  for (let i = 0; i < 40 && !leaf(FEEDBACK); i++) await sleep(500);
  const fbTab = leaf(FEEDBACK), trTab = leaf(TRANSCRIPT);
  if (!fbTab || !trTab) return { error: 'tabs_not_found' };

  fbTab.click();
  await sleep(2500);
  const feedbackLines = document.body.innerText.split('\n').map(s => s.trim()).filter(Boolean);

  trTab.click();
  let rows = [];
  for (let i = 0; i < 20 && rows.length === 0; i++) {
    await sleep(500);
    rows = [...document.querySelectorAll('img')]
      .filter(img => /camblyavatars/.test(img.src) && img.getBoundingClientRect().width <= 40)
      .map(img => {
        let row = img.parentElement;
        while (row && !(row.innerText || '').trim()) row = row.parentElement;
        return row ? [img.src.includes(userId) ? 'L' : 'T', row.innerText.trim()] : null;
      })
      .filter(Boolean);
  }
  return { feedbackLines, rows };
}
