const localHosts = new Set(['localhost', '127.0.0.1']);
const API_URL =
  window.API_URL ||
  (localHosts.has(window.location.hostname)
    ? `${window.location.protocol}//${window.location.hostname}:8000`
    : 'https://name-app-yj19.onrender.com');

const form = document.getElementById('blogForm');
const blogFormPanel = document.getElementById('blogFormPanel');
const blogList = document.getElementById('blogList');
const tagFilter = document.getElementById('tagFilter');
const userFilter = document.getElementById('userFilter');
const messageBox = document.getElementById('message');
const refreshBtn = document.getElementById('refreshBtn');
const logoutBtn = document.getElementById('logoutBtn');
const currentUserDisplay = document.getElementById('currentUser');
const cancelEditBtn = document.getElementById('cancelEditBtn');
const blogIdInput = document.getElementById('blogId');
const titleInput = document.getElementById('title');
const descriptionInput = document.getElementById('description');
const cityInput = document.getElementById('city');
const emailInput = document.getElementById('email');
const authorInput = document.getElementById('author');
const formTitle = document.getElementById('formTitle');
const saveBlogBtn = document.getElementById('saveBlogBtn');
const detailsDialog = document.getElementById('blogDetailsDialog');
const detailsList = document.getElementById('detailsList');
const detailsUpdateBtn = document.getElementById('detailsUpdateBtn');
const detailsDeleteBtn = document.getElementById('detailsDeleteBtn');
const loginForm = document.getElementById('loginForm');
const registerForm = document.getElementById('registerForm');
const authPanel = document.getElementById('authPanel');

let allBlogs = [];
let accessToken = null;
let csrfToken = null;
let hasRefreshSession = false;
let currentUser = null;
let editingBlogId = null;
let detailsBlogId = null;
let returnToDetailsId = null;
let refreshRequest = null;

function showMessage(message, type = 'success') {
  messageBox.textContent = message;
  messageBox.className = `message ${type}`;
}

function clearMessage() {
  messageBox.textContent = '';
  messageBox.className = 'message';
}

function messageForStatus(status, detail, fallback) {
  if (status === 401) return 'Please log in again to continue.';
  if (status === 403) return detail || 'You are not allowed to perform this action.';
  if (status === 409) return detail || 'That username or email is already registered.';
  if (status === 422) {
    if (Array.isArray(detail)) {
      return detail.map((item) => item.msg).filter(Boolean).join(' ') || 'Please check the entered values.';
    }
    return detail || 'Please check the entered values.';
  }
  if (status === 429) return 'Too many attempts. Please wait a few minutes and try again.';
  return detail || fallback;
}

async function readResponse(response, fallback) {
  let data;
  try {
    data = await response.json();
  } catch {
    if (response.ok) throw new Error('The server returned an invalid response.');
    data = {};
  }
  if (!response.ok) {
    throw new Error(messageForStatus(response.status, data.detail, fallback));
  }
  return data;
}

async function loadCsrfToken() {
  const response = await fetch(`${API_URL}/csrf`, { credentials: 'include' });
  const data = await readResponse(response, 'Unable to verify your session.');
  csrfToken = data.csrf_token;
  hasRefreshSession = Boolean(data.has_refresh_session);
  if (!csrfToken) throw new Error('The server did not return a CSRF token.');
  return true;
}

async function refreshAccessToken() {
  if (refreshRequest) return refreshRequest;

  refreshRequest = (async () => {
    try {
      if (!csrfToken && !(await loadCsrfToken())) return false;
      if (!hasRefreshSession) return false;
      const response = await fetch(`${API_URL}/refresh`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'X-CSRF-Token': csrfToken },
      });
      if (!response.ok) {
        hasRefreshSession = false;
        return false;
      }
      const data = await response.json();
      accessToken = data.access_token;
      csrfToken = data.csrf_token;
      hasRefreshSession = true;
      return Boolean(accessToken);
    } catch (error) {
      showMessage(
        error instanceof Error
          ? error.message
          : 'Unable to verify your session. Check your connection and try again.',
        'error',
      );
      return false;
    } finally {
      refreshRequest = null;
    }
  })();
  return refreshRequest;
}

async function authenticatedRequest(path, options = {}, retry = true) {
  if (!accessToken && !(await refreshAccessToken())) {
    throw new Error('Please log in to manage blogs.');
  }

  const headers = new Headers(options.headers || {});
  headers.set('Authorization', `Bearer ${accessToken}`);
  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers,
    credentials: 'include',
  });

  if (response.status === 401 && retry && (await refreshAccessToken())) {
    return authenticatedRequest(path, options, false);
  }
  if (response.status === 401) {
    clearSession();
    throw new Error('Your session expired. Please log in again.');
  }
  return readResponse(response, 'The request could not be completed.');
}

function clearSession() {
  accessToken = null;
  csrfToken = null;
  hasRefreshSession = false;
  currentUser = null;
  syncAuthUi();
}

function syncAuthUi() {
  const authenticated = Boolean(currentUser && accessToken);
  authPanel.classList.toggle('hidden', authenticated);
  blogFormPanel.classList.toggle('hidden', !authenticated);
  logoutBtn.classList.toggle('hidden', !authenticated);
  currentUserDisplay.classList.toggle('hidden', !authenticated);
  currentUserDisplay.textContent = authenticated
    ? `Signed in as ${currentUser.name}`
    : '';
  renderBlogs(allBlogs);
  if (detailsBlogId !== null) {
    const blog = allBlogs.find((item) => item.id === detailsBlogId);
    setDetailsPermissions(blog);
  }
}

function setDetailsPermissions(blog) {
  const isOwner = Boolean(
    currentUser && blog && Number(blog.user_id) === Number(currentUser.id),
  );
  detailsUpdateBtn.classList.toggle('hidden', !isOwner);
  detailsDeleteBtn.classList.toggle('hidden', !isOwner);
}

function getBlogFormData() {
  const selectedTags = document.querySelectorAll('input[name="tags"]:checked');
  return {
    title: titleInput.value.trim(),
    description: descriptionInput.value.trim(),
    city: cityInput.value.trim(),
    email: emailInput.value.trim(),
    author: authorInput.value.trim(),
    tag_ids: Array.from(selectedTags, (checkbox) => Number(checkbox.value)),
  };
}

function formatCreatedAt(value) {
  if (!value) return { date: 'Unavailable', time: 'Unavailable' };
  const createdAt = new Date(value);
  if (Number.isNaN(createdAt.getTime())) return { date: 'Unavailable', time: 'Unavailable' };
  return {
    date: new Intl.DateTimeFormat(undefined, {
      year: 'numeric',
      month: 'short',
      day: '2-digit',
    }).format(createdAt),
    time: new Intl.DateTimeFormat(undefined, {
      hour: '2-digit',
      minute: '2-digit',
    }).format(createdAt),
  };
}

function addText(parent, tagName, className, text) {
  const element = document.createElement(tagName);
  if (className) element.className = className;
  element.textContent = text;
  parent.append(element);
  return element;
}

function createActionButton(label, action, blogId, className) {
  const button = document.createElement('button');
  button.className = className;
  button.type = 'button';
  button.dataset.action = action;
  button.dataset.blogId = blogId;
  button.textContent = label;
  return button;
}

function renderBlogs(blogs) {
  blogList.replaceChildren();
  if (!Array.isArray(blogs)) {
    throw new Error('The blog list response was not valid.');
  }
  if (!blogs.length) {
    addText(blogList, 'div', 'empty-state', 'No blogs found yet.');
    return;
  }

  for (const blog of blogs) {
    const card = document.createElement('article');
    card.className = 'blog-card';
    const title = createActionButton(blog.title ?? '', 'view', blog.id, 'blog-title');
    title.setAttribute('aria-label', `View details for ${blog.title ?? 'blog'}`);
    card.append(title);

    const createdAt = formatCreatedAt(blog.date_created);
    const metadata = document.createElement('div');
    metadata.className = 'blog-meta';
    addText(metadata, 'p', '', `Created Date: ${createdAt.date}`);
    addText(metadata, 'p', '', `Created Time: ${createdAt.time}`);
    card.append(metadata);

    const actions = document.createElement('div');
    actions.className = 'card-actions';
    actions.append(createActionButton('View Details', 'view', blog.id, 'view-btn'));
    if (currentUser && Number(blog.user_id) === Number(currentUser.id)) {
      actions.append(
        createActionButton('Update', 'update', blog.id, 'edit-btn'),
        createActionButton('Delete', 'delete', blog.id, 'delete-btn'),
      );
    }
    card.append(actions);
    blogList.append(card);
  }
}

function populateUserFilter() {
  const selectedUser = userFilter.value;
  const users = new Map();
  allBlogs.forEach((blog) => {
    if (blog.user_id !== null && blog.user_name) {
      users.set(String(blog.user_id), blog.user_name);
    }
  });
  userFilter.replaceChildren(new Option('All Users', 'All'));
  users.forEach((name, id) => userFilter.add(new Option(name, id)));
  userFilter.value = users.has(selectedUser) ? selectedUser : 'All';
}

function filterBlogs() {
  const selectedTag = tagFilter.value;
  const selectedUser = userFilter.value;
  renderBlogs(
    allBlogs.filter((blog) => {
      const matchesTag = selectedTag === 'All' || blog.tags?.includes(selectedTag);
      const matchesUser = selectedUser === 'All' || String(blog.user_id) === selectedUser;
      return matchesTag && matchesUser;
    }),
  );
}

async function loadBlogs() {
  try {
    const response = await fetch(`${API_URL}/blogs`, { credentials: 'include' });
    const blogs = await readResponse(response, 'Unable to load blogs.');
    if (!Array.isArray(blogs)) throw new Error('The blog list response was not valid.');
    allBlogs = blogs;
    populateUserFilter();
    filterBlogs();
  } catch (error) {
    showMessage(error.message, 'error');
  }
}

function setFormMode(isEditing) {
  formTitle.textContent = isEditing ? 'Update Blog' : 'Create Blog';
  saveBlogBtn.textContent = isEditing ? 'Update Blog' : 'Save Blog';
  cancelEditBtn.classList.toggle('hidden', !isEditing);
}

function resetForm() {
  form.reset();
  editingBlogId = null;
  blogIdInput.value = '';
  setFormMode(false);
}

function closeDetails() {
  if (detailsDialog.open) detailsDialog.close();
  detailsBlogId = null;
}

async function openBlogDetails(blogId) {
  try {
    const response = await fetch(`${API_URL}/blogs/${blogId}`, { credentials: 'include' });
    const blog = await readResponse(response, 'Unable to load blog details.');
    const createdAt = formatCreatedAt(blog.date_created);
    const fields = [
      ['Blog ID', blog.id],
      ['Blog Title', blog.title],
      ['Full Description', blog.description],
      ['Author Name', blog.author],
      ['City', blog.city],
      ['Email', blog.email],
      ['Created Date', createdAt.date],
      ['Created Time', createdAt.time],
    ];
    detailsList.replaceChildren();
    for (const [label, value] of fields) {
      addText(detailsList, 'dt', '', label);
      addText(detailsList, 'dd', '', value ?? '');
    }
    detailsBlogId = blog.id;
    setDetailsPermissions(blog);
    if (!detailsDialog.open) detailsDialog.showModal();
  } catch (error) {
    showMessage(error.message, 'error');
  }
}

async function startEdit(blogId) {
  try {
    const response = await fetch(`${API_URL}/blogs/${blogId}`, { credentials: 'include' });
    const blog = await readResponse(response, 'Unable to load blog details.');
    if (!currentUser || Number(blog.user_id) !== Number(currentUser.id)) {
      throw new Error('You may manage only your own blogs.');
    }
    returnToDetailsId = detailsDialog.open && detailsBlogId === blog.id ? blog.id : null;
    closeDetails();
    editingBlogId = blog.id;
    blogIdInput.value = blog.id;
    titleInput.value = blog.title ?? '';
    descriptionInput.value = blog.description ?? '';
    cityInput.value = blog.city ?? '';
    emailInput.value = blog.email ?? '';
    authorInput.value = blog.author ?? '';
    const selectedTagIds = new Set(blog.tag_ids ?? []);
    document.querySelectorAll('input[name="tags"]').forEach((checkbox) => {
      checkbox.checked = selectedTagIds.has(Number(checkbox.value));
    });
    setFormMode(true);
    clearMessage();
    window.scrollTo({ top: 0, behavior: 'smooth' });
    titleInput.focus({ preventScroll: true });
  } catch (error) {
    showMessage(error.message, 'error');
  }
}

async function deleteBlog(blogId) {
  try {
    const response = await fetch(`${API_URL}/blogs/${blogId}`, { credentials: 'include' });
    const blog = await readResponse(response, 'Unable to load blog details.');
    if (!currentUser || Number(blog.user_id) !== Number(currentUser.id)) {
      throw new Error('You may manage only your own blogs.');
    }
    if (!window.confirm(`Delete "${blog.title}"? This action cannot be undone.`)) return;
    await authenticatedRequest(`/blogs/${blogId}`, { method: 'DELETE' });
    if (editingBlogId === blogId) resetForm();
    if (detailsBlogId === blogId) closeDetails();
    if (returnToDetailsId === blogId) returnToDetailsId = null;
    showMessage('Blog deleted successfully.');
    await loadBlogs();
  } catch (error) {
    showMessage(error.message, 'error');
  }
}

async function saveBlog(event) {
  event.preventDefault();
  clearMessage();
  const isEditing = editingBlogId !== null;
  const path = isEditing ? `/blogs/${editingBlogId}` : '/blogs';
  saveBlogBtn.disabled = true;
  saveBlogBtn.textContent = 'Saving…';
  try {
    await authenticatedRequest(path, {
      method: isEditing ? 'PUT' : 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(getBlogFormData()),
    });
    const refreshedDetailsId = returnToDetailsId;
    returnToDetailsId = null;
    resetForm();
    showMessage(isEditing ? 'Blog updated successfully.' : 'Blog created successfully.');
    await loadBlogs();
    if (refreshedDetailsId !== null) await openBlogDetails(refreshedDetailsId);
  } catch (error) {
    showMessage(error.message, 'error');
  } finally {
    saveBlogBtn.disabled = false;
    saveBlogBtn.textContent = editingBlogId !== null ? 'Update Blog' : 'Save Blog';
  }
}

async function login(identifier, password) {
  const response = await fetch(`${API_URL}/login`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({ username: identifier, password }),
  });
  const data = await readResponse(response, 'Unable to log in.');
  accessToken = data.access_token;
  csrfToken = data.csrf_token;
  hasRefreshSession = true;
  currentUser = data.user;
  syncAuthUi();
  await loadBlogs();
}

async function withLoading(button, loadingText, action) {
  const originalText = button.textContent;
  button.disabled = true;
  button.textContent = loadingText;
  try {
    await action();
  } finally {
    button.disabled = false;
    button.textContent = originalText;
  }
}

function resetAuthForm(authForm) {
  authForm.reset();
  authForm.querySelectorAll('[data-toggle-password]').forEach((button) => {
    document.getElementById(button.dataset.togglePassword).type = 'password';
    button.textContent = 'Show';
  });
}

blogList.addEventListener('click', (event) => {
  const button = event.target.closest('button[data-action]');
  if (!button) return;
  const blogId = Number(button.dataset.blogId);
  if (button.dataset.action === 'view') openBlogDetails(blogId);
  if (button.dataset.action === 'update') startEdit(blogId);
  if (button.dataset.action === 'delete') deleteBlog(blogId);
});

form.addEventListener('submit', saveBlog);
tagFilter.addEventListener('change', filterBlogs);
userFilter.addEventListener('change', filterBlogs);

loginForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const button = document.getElementById('loginBtn');
  clearMessage();
  await withLoading(button, 'Logging in…', async () => {
    try {
      await login(
        document.getElementById('loginIdentifier').value.trim(),
        document.getElementById('loginPassword').value,
      );
      resetAuthForm(loginForm);
      showMessage('You are now logged in.');
    } catch (error) {
      showMessage(error.message, 'error');
    }
  });
});

registerForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const button = document.getElementById('registerBtn');
  clearMessage();
  await withLoading(button, 'Creating account…', async () => {
    const account = Object.fromEntries(new FormData(registerForm));
    try {
      const response = await fetch(`${API_URL}/register`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(account),
      });
      await readResponse(response, 'Unable to create account.');
      await login(account.username, account.password);
      resetAuthForm(registerForm);
      showMessage('Account created and logged in.');
    } catch (error) {
      showMessage(error.message, 'error');
    }
  });
});

logoutBtn.addEventListener('click', async () => {
  logoutBtn.disabled = true;
  try {
    if (!accessToken) await refreshAccessToken();
    if (accessToken && csrfToken) {
      await authenticatedRequest('/logout', {
        method: 'POST',
        headers: { 'X-CSRF-Token': csrfToken },
      });
    }
    clearSession();
    showMessage('You are logged out.');
  } catch (error) {
    clearSession();
    showMessage(error.message, 'error');
  } finally {
    logoutBtn.disabled = false;
  }
});

document.querySelectorAll('[data-toggle-password]').forEach((button) => {
  button.addEventListener('click', () => {
    const input = document.getElementById(button.dataset.togglePassword);
    const showing = input.type === 'password';
    input.type = showing ? 'text' : 'password';
    button.textContent = showing ? 'Hide' : 'Show';
  });
});

cancelEditBtn.addEventListener('click', async () => {
  const blogId = returnToDetailsId;
  returnToDetailsId = null;
  resetForm();
  clearMessage();
  if (blogId !== null) await openBlogDetails(blogId);
});
refreshBtn.addEventListener('click', () => {
  clearMessage();
  loadBlogs();
});
detailsUpdateBtn.addEventListener('click', () => {
  if (detailsBlogId !== null) startEdit(detailsBlogId);
});
detailsDeleteBtn.addEventListener('click', () => {
  if (detailsBlogId !== null) deleteBlog(detailsBlogId);
});
document.getElementById('closeDetailsBtn').addEventListener('click', closeDetails);
document.getElementById('closeDetailsIcon').addEventListener('click', closeDetails);
detailsDialog.addEventListener('click', (event) => {
  if (event.target === detailsDialog) closeDetails();
});
detailsDialog.addEventListener('close', () => {
  detailsBlogId = null;
});

async function restoreSession() {
  try {
    await loadCsrfToken();
    if (await refreshAccessToken()) {
      const response = await fetch(`${API_URL}/me`, {
        headers: { Authorization: `Bearer ${accessToken}` },
        credentials: 'include',
      });
      currentUser = await readResponse(response, 'Unable to restore session.');
    }
  } catch (error) {
    if (accessToken) {
      clearSession();
    }
    showMessage(error.message, 'error');
  }
  syncAuthUi();
}

syncAuthUi();
loadBlogs();
restoreSession();
