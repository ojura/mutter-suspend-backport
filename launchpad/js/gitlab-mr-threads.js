(async () => {
  // expand collapsed replies
  for (const b of document.querySelectorAll('button')) {
    if (/replies|Show all|Expand/i.test(b.innerText)) { try { b.click(); } catch (e) {} }
  }
  await new Promise(r => setTimeout(r, 2500));
  const disc = [...document.querySelectorAll('.discussion-notes, .discussion, .timeline-entry .note-body, .notes .note')]
    .map(n => n.innerText.replace(/\n{2,}/g, '\n').trim()).filter(t => t.length > 40);
  return [...new Set(disc)].join('\n=====\n').slice(0, 20000);
})()
