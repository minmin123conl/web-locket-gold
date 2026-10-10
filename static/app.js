(() => {
  const form = document.querySelector('#activateForm');
  const input = document.querySelector('#username');
  const button = document.querySelector('#submitBtn');
  const panel = document.querySelector('#resultPanel');
  const icon = document.querySelector('#resultIcon');
  const title = document.querySelector('#resultTitle');
  const message = document.querySelector('#resultMessage');
  const source = document.querySelector('#resultSource');
  const uid = document.querySelector('#resultUid');
  const status = document.querySelector('#resultStatus');
  const expires = document.querySelector('#resultExpires');
  const guide = document.querySelector('#downloadGuide');

  if (!form || !input || !button || !panel) return;

  const setClearState = () => { clear.hidden = input.value.length === 0; };
  input.addEventListener('input', setClearState);
  clear?.addEventListener('click', () => { input.value = ''; input.focus(); setClearState(); });

  const setLoading = (loading) => { button.disabled = loading; button.textContent = loading ? 'Đang kíchactivate…' : 'Kíchactivate Gold ngay'; };

  const showResult = (data, isError = false) => {
    const active = Boolean(data.active);
    panel.hidden = false;
    panel.classList.toggle('is-error', isError || !active);
    icon.textContent = isError ? '✕' : active ? '✓' : '—';
    title.textContent = isError ? 'Không thể kíchactivate' : active ? 'Gold đang hoạtactivate!' : 'Chưa kíchactivate';
    message.textContent = data.message || data.error || 'Đã kiểm tra xong.';
    source.textContent = (data.source || 'remote').toUpperCase();
    uid.textContent = data.uid || '—';
    status.textContent = isError ? 'Lỗi' : active ? 'Active' : 'Inactive';
    expires.textContent = data.expires || '—';
    guide.hidden = isError || !data.guide_file;
    panel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  };

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const value = input.value.trim();
    if (!value) { showResult({ error: 'Vui lòng nhập UID hoặc link hồ sơ Locket.' }, true); input.focus(); return; }
    setLoading(true);
    try {
      const response = await fetch('/activate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
        body: JSON.stringify({ username: value }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Yêu cầu không hợp lệ.');
      showResult(data);
    } catch (error) { showResult({ error: error.message || 'Không thể kết nối máy chủ.' }, true); } finally { setLoading(false); }
  });
})();