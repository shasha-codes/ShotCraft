(() => {
  const escapeHtml = value => String(value || '').replace(/[&<>'"]/g, character => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[character]));
  const workspaceFor = user => user.user_type === 'photographer' ? '/photographer' : '/client';

  async function signOut() {
    try { await fetch('/api/auth/logout', {method: 'POST'}); }
    finally { window.location.reload(); }
  }

  async function showSignedInState() {
    let response;
    try { response = await fetch('/api/auth/me', {cache: 'no-store'}); }
    catch { return; }
    if (!response.ok) return;
    const user = await response.json();
    const workspace = workspaceFor(user);
    const label = user.user_type === 'photographer' ? 'Photographer workspace' : 'Client workspace';
    const auth = document.getElementById('landingAuth');
    if (!auth) return;

    auth.innerHTML = `<span class="signed-in">Signed in as <b>${escapeHtml(user.name)}</b></span><a class="signup" href="${workspace}">Open workspace <span>→</span></a><button class="landing-signout" type="button">Sign out</button>`;
    auth.querySelector('.landing-signout').addEventListener('click', signOut);
    const setWorkspaceLink = (selector, copy = 'Open workspace <span>→</span>') => {
      const link = document.querySelector(selector);
      if (!link) return;
      link.href = workspace;
      link.innerHTML = copy;
    };
    setWorkspaceLink('.hero-actions .button.primary');
    setWorkspaceLink('.statement-copy .button.dark');
    setWorkspaceLink('.closing .button.primary');
    const closingSignOut = document.querySelector('.closing .button.ghost');
    if (closingSignOut) {
      closingSignOut.href = '#top';
      closingSignOut.textContent = 'Sign out';
      closingSignOut.addEventListener('click', event => {
        event.preventDefault();
        signOut();
      });
    }
    const featureLink = document.querySelector('.feature-ink a');
    if (featureLink) featureLink.textContent = `${label} →`;
  }

  showSignedInState();
})();
