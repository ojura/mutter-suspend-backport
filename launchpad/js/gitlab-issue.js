(async () => {
  for (let i = 0; i < 15 && !document.querySelector('.description, [data-testid="work-item-description"], .work-item-description'); i++)
    await new Promise(r => setTimeout(r, 1000));
  await new Promise(r => setTimeout(r, 2500));
  const title = document.querySelector('h1')?.innerText;
  const desc = document.querySelector('[data-testid="work-item-description"], .work-item-description, .description')?.innerText;
  const notes = [...document.querySelectorAll('.note-body, .timeline-entry .note-text, [data-testid="work-item-note"], .note')]
    .map(n => n.innerText.replace(/\n{2,}/g, '\n').trim().slice(0, 1200));
  const refs = [...document.querySelectorAll('a')].map(a => a.href).filter(h => /mutter\/-\/(merge_requests|issues|commit)\/\w+/.test(h));
  return JSON.stringify({url: location.href, title, desc: desc?.slice(0, 3000), notes: [...new Set(notes)].slice(0, 25), refs: [...new Set(refs)].slice(0, 40)}, null, 1);
})()
