(() => {
  const form = document.querySelector('#activateForm');
  const input = document.querySelector('#username');
  const clear = document.querySelector('#clearInput');
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

  const setClearState = () => { clear.hidden = input.value.length === 0; };
  input.addEventListener('input', setClearState);
  clear.addEventListener('click', () => { input.value = ''; input.focus(); setClearState(); });

  const showResult = (data, isError = false) => {
    panel.hidden = false;
    panel.classList.toggle('is-error', isError || !data.active);
    icon.textContent = isError ? '!' : (data.active ? '✓' : '—');
    title.textContent = isError ? 'Không thể kiểm tra' : (data.active ? 'Trạng thái đang hoạt động' : 'Chưa có trạng thái hoạt động');
    message.textContent = data.message || data.error || 'Đã hoàn tất kiểm tra.';
    source.textContent = (data.source || 'demo').toUpperCase();
    uid.textContent = data.uid || '—';
    status.textContent = isError ? 'Lỗi' : (data.active ? 'Active' : 'Inactive');
    expires.textContent = data.expires || '—';
    guide.hidden = isError || !data.guide_file;
    panel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  };

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const value = input.value.trim();
    if (!value) { showResult({ error: 'Vui lòng nhập UID hoặc link hồ sơ.' }, true); input.focus(); return; }
    button.disabled = true;
    button.querySelector('span').textContent = 'Đang kiểm tra…';
    try {
      const response = await fetch('/activate', { method: 'POST', headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' }, body: JSON.stringify({ username: value }) });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Yêu cầu không hợp lệ.');
      showResult(data);
    } catch (error) { showResult({ error: error.message }, true); }
    finally { button.disabled = false; button.querySelector('span').textContent = 'Kiểm tra trạng thái'; }
  });
})();
