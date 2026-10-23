const API_URL = 'http://0.0.0.0:8000';

const form = document.getElementById('blogForm');
const blogList = document.getElementById('blogList');
const tagFilter = document.getElementById('tagFilter');
const messageBox = document.getElementById('message');
const refreshBtn = document.getElementById('refreshBtn');
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
const userFilter = document.getElementById('userFilter');
const userIdInput = document.getElementById('userId');
let allBlogs = [];
let editingBlogId = null;
let detailsBlogId = null;
let returnToDetailsId = null;

function showMessage(text, type = 'success') {
  messageBox.textContent = text;
  messageBox.className = `message ${type}`;
}

function clearMessage() {
  messageBox.textContent = '';
  messageBox.className = 'message';
}

function responseError(data, fallback) {
  if (Array.isArray(data.detail)) {
    return data.detail.map((item) => item.msg).filter(Boolean).join(' ') || fallback;
  }
  return data.detail || fallback;
}

async function readResponse(response, fallback) {
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(responseError(data, fallback));
  }
  return data;
}


function getFormData() {
    const selectedTags = document.querySelectorAll(
        'input[name="tags"]:checked'
    );

    const tagIds = Array.from(selectedTags).map(
        checkbox => Number(checkbox.value)
    );

    return {
        title: titleInput.value.trim(),
        description: descriptionInput.value.trim(),
        city: cityInput.value.trim(),
        email: emailInput.value.trim(),
        author: authorInput.value.trim(),
        tag_ids: tagIds,
        user_id: Number(userIdInput.value)
    };
}


function formatCreatedAt(value) {
  if (!value) {
    return { date: 'Unavailable', time: 'Unavailable' };
  }

  const createdAt = new Date(value);
  if (Number.isNaN(createdAt.getTime())) {
    return { date: 'Unavailable', time: 'Unavailable' };
  }

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
  if (className) {
    element.className = className;
  }
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
    actions.append(
      createActionButton('View Details', 'view', blog.id, 'view-btn'),
      createActionButton('Update', 'update', blog.id, 'edit-btn'),
      createActionButton('Delete', 'delete', blog.id, 'delete-btn'),
    );
    card.append(actions);
    blogList.append(card);
  }
}



async function loadUsers() {
    try {
        const response = await fetch(`${API_URL}/users`);
        const users = await readResponse(
            response,
            'Unable to load users.'
        );

        const selectedUser = userIdInput.value;
        const selectedFilter = userFilter.value;

        // Create Blog dropdown
        userIdInput.replaceChildren(
            new Option('Select User', '')
        );

        // Filter Blogs dropdown
        userFilter.replaceChildren(
            new Option('All Users', 'All')
        );

        users.forEach(user => {
            userIdInput.add(
                new Option(user.name, String(user.id))
            );

            userFilter.add(
                new Option(user.name, String(user.id))
            );
        });

        if (users.some(u => String(u.id) === selectedUser)) {
            userIdInput.value = selectedUser;
        }

        if (users.some(u => String(u.id) === selectedFilter)) {
            userFilter.value = selectedFilter;
        }

        filterBlogs();

    } catch (error) {
        showMessage(error.message, 'error');
    }
}


function populateUserFilter() {
    const selectedUser = userFilter.value;
    const users = new Map();

    allBlogs.forEach(blog => {
        if (blog.user_id != null && blog.user_name) {
            users.set(String(blog.user_id), blog.user_name);
        }
    });

    userFilter.replaceChildren(new Option('All Users', 'All'));

    users.forEach((name, id) => {
        userFilter.add(new Option(name, id));
    });

    userFilter.value = users.has(selectedUser)
        ? selectedUser
        : 'All';
}

function filterBlogs() {
    const selectedTag = tagFilter.value;
    const selectedUser = userFilter.value;

    const filteredBlogs = allBlogs.filter(blog => {
        const matchesTag =
            selectedTag === 'All' ||
            (Array.isArray(blog.tags) &&
             blog.tags.includes(selectedTag));

        const matchesUser =
            selectedUser === 'All' ||
            String(blog.user_id) === selectedUser;

        return matchesTag && matchesUser;
    });

    renderBlogs(filteredBlogs);
}


async function loadBlogs() {
  try {
    const response = await fetch(`${API_URL}/blogs`);
    const blogs = await readResponse(response, 'Unable to load blogs.');

    if (!Array.isArray(blogs)) {
      throw new Error('The blog list response was not valid.');
    }

    allBlogs = blogs;
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
  if (detailsDialog.open) {
    detailsDialog.close();
  }
  detailsBlogId = null;
}

tagFilter.addEventListener('change', filterBlogs);
userFilter.addEventListener('change', filterBlogs);


async function openBlogDetails(blogId) {
  try {
    const response = await fetch(`${API_URL}/blogs/${blogId}`);
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
    if (!detailsDialog.open) {
      detailsDialog.showModal();
    }
  } catch (error) {
    showMessage(error.message, 'error');
  }
}

async function startEdit(blogId) {
  try {
    const response = await fetch(`${API_URL}/blogs/${blogId}`);
    const blog = await readResponse(response, 'Unable to load blog details.');
    returnToDetailsId = detailsDialog.open && detailsBlogId === blog.id ? blog.id : null;
    closeDetails();
    editingBlogId = blog.id;
    blogIdInput.value = blog.id;
    titleInput.value = blog.title ?? '';
    descriptionInput.value = blog.description ?? '';
    cityInput.value = blog.city ?? '';
    emailInput.value = blog.email ?? '';
    authorInput.value = blog.author ?? '';
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
    const detailResponse = await fetch(`${API_URL}/blogs/${blogId}`);
    const blog = await readResponse(detailResponse, 'Unable to load blog details.');
    const confirmed = window.confirm(`Delete "${blog.title}"? This action cannot be undone.`);
    if (!confirmed) {
      return;
    }

    const response = await fetch(`${API_URL}/blogs/${blogId}`, { method: 'DELETE' });
    await readResponse(response, 'Unable to delete blog.');

    if (editingBlogId === blogId) {
      resetForm();
    }
    if (detailsBlogId === blogId) {
      closeDetails();
    }
    if (returnToDetailsId === blogId) {
      returnToDetailsId = null;
    }
    showMessage('Blog deleted successfully.');
    await loadBlogs();
  } catch (error) {
    showMessage(error.message, 'error');
  }
}

async function saveBlog(event) {
  event.preventDefault();
  clearMessage();

  const payload = getFormData();
  const isEditing = editingBlogId !== null;
  const url = isEditing ? `${API_URL}/blogs/${editingBlogId}` : `${API_URL}/blogs`;

  try {
    const response = await fetch(url, {
      method: isEditing ? 'PUT' : 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    await readResponse(response, isEditing ? 'Unable to update blog.' : 'Unable to create blog.');

    const refreshedDetailsId = returnToDetailsId;
    returnToDetailsId = null;
    resetForm();
    showMessage(isEditing ? 'Blog updated successfully.' : 'Blog created successfully.');
    await loadBlogs();
    if (refreshedDetailsId !== null) {
      await openBlogDetails(refreshedDetailsId);
    }
  } catch (error) {
    showMessage(error.message, 'error');
  }
}

blogList.addEventListener('click', (event) => {
  const button = event.target.closest('button[data-action]');
  if (!button) {
    return;
  }

  const blogId = Number(button.dataset.blogId);
  if (button.dataset.action === 'view') {
    openBlogDetails(blogId);
  } else if (button.dataset.action === 'update') {
    startEdit(blogId);
  } else if (button.dataset.action === 'delete') {
    deleteBlog(blogId);
  }
});

form.addEventListener('submit', saveBlog);
cancelEditBtn.addEventListener('click', async () => {
  const blogId = returnToDetailsId;
  returnToDetailsId = null;
  resetForm();
  clearMessage();
  if (blogId !== null) {
    await openBlogDetails(blogId);
  }
});
refreshBtn.addEventListener('click', () => {
  clearMessage();
  loadBlogs();
});
detailsUpdateBtn.addEventListener('click', () => {
  if (detailsBlogId !== null) {
    startEdit(detailsBlogId);
  }
});
detailsDeleteBtn.addEventListener('click', () => {
  if (detailsBlogId !== null) {
    deleteBlog(detailsBlogId);
  }
});
document.getElementById('closeDetailsBtn').addEventListener('click', closeDetails);
document.getElementById('closeDetailsIcon').addEventListener('click', closeDetails);
detailsDialog.addEventListener('click', (event) => {
  if (event.target === detailsDialog) {
    closeDetails();
  }
});
detailsDialog.addEventListener('close', () => {
  detailsBlogId = null;
});

const userForm = document.getElementById('userForm');

userForm.addEventListener('submit', async (event) => {
    event.preventDefault();

    const name = document.getElementById('newUserName').value.trim();

    if (!name) return;

    try {
        const response = await fetch(`${API_URL}/users`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ name })
        });

        if (!response.ok) {
            throw new Error('Unable to create user');
        }

        userForm.reset();

        await loadUsers();

        showMessage('User created successfully');

    } catch (error) {
        showMessage(error.message, 'error');
    }
});

loadBlogs();
loadUsers();
