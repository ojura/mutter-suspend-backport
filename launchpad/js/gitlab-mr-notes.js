(async () => {
  for (let i = 0; i < 10 && !document.querySelector('.note, .timeline-entry'); i++)
    await new Promise(r => setTimeout(r, 1000));
  const notes = [...document.querySelectorAll('.timeline-entry, .note')].map(n => n.innerText.replace(/\s+/g, ' ').trim().slice(0, 300));
  const issueLinks = [...document.querySelectorAll('a')].map(a => a.href).filter(h => /\/(issues|merge_requests)\/\d+/.test(h));
  const meta = [...document.querySelectorAll('.merge-request-tabs, .mr-widget-body, .mr-state-widget')].map(e => e.innerText.slice(0, 500));
  return JSON.stringify({notes: [...new Set(notes)].slice(0, 60), issueLinks: [...new Set(issueLinks)], meta}, null, 1);
})()
