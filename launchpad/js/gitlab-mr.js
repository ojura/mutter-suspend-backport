(async () => {
  await new Promise(r => setTimeout(r, 3000));
  const title = document.querySelector('h1')?.innerText;
  const desc = document.querySelector('.detail-page-description .md, .description .md')?.innerText;
  const links = [...document.querySelectorAll('.detail-page-description a, .description a')].map(a => a.href);
  const state = document.querySelector('.issuable-status-badge, .badge-state, [data-testid="merge-request-state-badge"]')?.innerText;
  const closing = [...document.querySelectorAll('a[href*="/issues/"]')].map(a => a.href + ' | ' + a.innerText.trim().slice(0,80));
  return JSON.stringify({url: location.href, title, state, desc, links, closing: [...new Set(closing)].slice(0, 40)}, null, 1);
})()
