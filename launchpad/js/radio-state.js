(() => JSON.stringify([...document.querySelectorAll("input[type=radio]")].map(r => ({id: r.id, checked: r.checked}))))()
