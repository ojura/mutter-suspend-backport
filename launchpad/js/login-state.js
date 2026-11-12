(async () => {
  await new Promise(r => setTimeout(r, 1500));
  const login = [...document.querySelectorAll('a')].filter(a => /log in|sign in/i.test(a.innerText)).map(a => a.innerText.trim());
  const me = document.querySelector('a[href^="https://launchpad.net/~"], .login-logout a, #logincontrol a, a.sprite.person')?.innerText;
  const header = document.querySelector('#logincontrol, .login-logout')?.innerText;
  return JSON.stringify({url: location.href, loginLinks: login, personLink: me, header});
})()
