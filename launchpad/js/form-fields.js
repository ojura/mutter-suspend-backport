(async () => {
  await new Promise(r => setTimeout(r, 3000));
  const inputs = [...document.querySelectorAll('input')].filter(i => i.type !== 'hidden').map(i => {
    const r = i.getBoundingClientRect();
    let autofilled = false;
    try { autofilled = i.matches(':autofill') || i.matches(':-webkit-autofill'); } catch (e) {}
    return {name: i.name, id: i.id, type: i.type, autofilled, hasValue: i.value.length > 0,
            box: [Math.round(r.x), Math.round(r.y), Math.round(r.width), Math.round(r.height)]};
  });
  const buttons = [...document.querySelectorAll('button, input[type=submit]')].map(b => {
    const r = b.getBoundingClientRect();
    return {text: (b.innerText || b.value || '').trim().slice(0, 40), box: [Math.round(r.x), Math.round(r.y), Math.round(r.width), Math.round(r.height)]};
  });
  return JSON.stringify({url: location.href, title: document.title, inputs, buttons}, null, 1);
})()
