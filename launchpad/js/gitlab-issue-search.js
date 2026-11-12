(async () => {
  for (let i = 0; i < 15 && !document.querySelector('.issuable-list li, [data-testid="issuable-container"], .issue'); i++)
    await new Promise(r => setTimeout(r, 1000));
  await new Promise(r => setTimeout(r, 1500));
  const items = [...document.querySelectorAll('.issuable-list > li, li.issue, [data-testid="issuable-container"]')]
    .map(li => li.innerText.replace(/\s+/g, ' ').trim().slice(0, 200));
  const empty = document.querySelector('.empty-state, [data-testid="issuable-empty-state"]')?.innerText;
  return JSON.stringify({url: location.href, count: items.length, items: items.slice(0, 30), empty}, null, 1);
})()
