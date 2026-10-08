const fallbackImage = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 1200 800'%3E%3Crect width='1200' height='800' fill='%230b3a8c'/%3E%3Ctext x='50%25' y='50%25' text-anchor='middle' fill='white' font-size='46' font-family='Arial'%3EIndia Cricket%3C/text%3E%3C/svg%3E";

const articleGrid = document.getElementById('blogGrid');
const articleCount = document.getElementById('blogCount');
const articleContent = document.getElementById('articleContent');
const relatedArticles = document.getElementById('relatedArticles');
const backToBlogs = document.getElementById('backToBlogs');

const blogArticles = Array.isArray(window.blogs) ? window.blogs : [];

function safeImage(image, title, className = '') {
  const img = document.createElement('img');
  img.src = image;
  img.alt = title;
  img.loading = 'lazy';
  img.className = className;
  img.onerror = () => {
    img.src = fallbackImage;
    img.alt = `${title} image unavailable`;
  };
  return img;
}

function renderContentParagraph(paragraph, index, total) {
  if (index === total - 1) {
    return `<div class="key-takeaway"><strong>Key takeaway:</strong> ${paragraph}</div>`;
  }

  if (paragraph.startsWith('### ')) {
    return `<h2>${paragraph.replace(/^###\s+/, '')}</h2>`;
  }

  if (paragraph.startsWith('## ')) {
    return `<h2>${paragraph.replace(/^##\s+/, '')}</h2>`;
  }

  return `<p>${paragraph}</p>`;
}

function formatArticle(blog) {
  return `
    <div class="article-image-wrap">
      ${safeImage(blog.image, blog.title).outerHTML}
      <div class="image-credit">Image: ${blog.imageAuthor || 'Wikimedia Commons'} • ${blog.imageLicense || 'License details on Commons'} • <a href="${blog.imageSource || 'https://commons.wikimedia.org/'}" target="_blank" rel="noopener noreferrer">View source</a></div>
    </div>
    <div class="article-text">
      <p class="eyebrow dark">${blog.category}</p>
      <h1>${blog.title}</h1>
      <div class="article-meta">
        <span><strong>By</strong> ${blog.author}</span>
        <span>•</span>
        <span>${blog.date}</span>
      </div>
      ${blog.content.map((paragraph, index) => renderContentParagraph(paragraph, index, blog.content.length)).join('')}
    </div>
  `;
}

function renderCards() {
  articleGrid.innerHTML = '';
  articleCount.textContent = `${blogArticles.length} article${blogArticles.length === 1 ? '' : 's'}`;

  blogArticles.forEach(blog => {
    const card = document.createElement('article');
    card.className = 'blog-card';
    card.innerHTML = `
      <div class="blog-card-image">
        ${safeImage(blog.image, blog.title).outerHTML}
      </div>
      <div class="blog-card-content">
        <span class="category">${blog.category}</span>
        <h3>${blog.title}</h3>
        <p>${blog.description}</p>
        <div class="blog-meta">
          <span>${blog.author}</span>
          <span>•</span>
          <span>${blog.date}</span>
        </div>
        <a class="card-button" href="blog.html?id=${blog.id}">Read More</a>
      </div>
    `;
    articleGrid.appendChild(card);
  });
}

function renderHomePage() {
  if (!articleGrid || !articleCount) return;
  renderCards();
}

function renderRelatedArticles(currentId) {
  const related = blogArticles.filter(blog => blog.id !== currentId).slice(0, 3);
  relatedArticles.innerHTML = '';

  related.forEach(blog => {
    const card = document.createElement('article');
    card.className = 'related-card';
    card.innerHTML = `
      <div class="related-card-image">
        ${safeImage(blog.image, blog.title).outerHTML}
      </div>
      <div class="related-card-body">
        <h3>${blog.title}</h3>
        <p>${blog.category}</p>
      </div>
    `;
    const link = document.createElement('a');
    link.href = `blog.html?id=${blog.id}`;
    link.setAttribute('aria-label', `Read ${blog.title}`);
    link.appendChild(card);
    relatedArticles.appendChild(link);
  });
}

function renderBlogPage() {
  if (!articleContent) return;
  const params = new URLSearchParams(window.location.search);
  const id = Number(params.get('id'));
  const blog = window.findBlogById(id);

  if (!blog) {
    articleContent.innerHTML = '<div class="article-text"><h1>Article not found</h1><p>The requested article may have been moved or no longer exists.</p><a class="card-button" href="index.html#blogs">Return to blogs</a></div>';
    return;
  }

  articleContent.innerHTML = formatArticle(blog);
  renderRelatedArticles(blog.id);
  if (backToBlogs) backToBlogs.href = `index.html#blogs`;
}

function initializeBlogApp() {
  if (window.__blogAppInitialized) return;
  window.__blogAppInitialized = true;

  if (articleGrid) renderHomePage();
  if (articleContent) renderBlogPage();
}

window.initializeBlogApp = initializeBlogApp;

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initializeBlogApp, { once: true });
} else {
  initializeBlogApp();
}
