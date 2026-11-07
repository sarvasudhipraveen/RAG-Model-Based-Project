// DocuRAG Studio - Frontend Logic
document.addEventListener('DOMContentLoaded', () => {
  // Application State
  const state = {
    currentProjectId: null,
    currentProject: null,
    projects: [],
    providers: {},
    workspaceFiles: [],
    settings: {
      provider: localStorage.getItem('rag_provider') || 'gemini',
      topK: parseInt(localStorage.getItem('rag_top_k') || '4', 10),
      keys: {
        gemini: localStorage.getItem('rag_key_gemini') || '',
        groq: localStorage.getItem('rag_key_groq') || '',
        openai: localStorage.getItem('rag_key_openai') || ''
      },
      models: {
        gemini: localStorage.getItem('rag_model_gemini') || 'gemini-3.5-flash-lite',
        groq: localStorage.getItem('rag_model_groq') || 'llama-3.3-70b-versatile',
        openai: localStorage.getItem('rag_model_openai') || 'gpt-4o-mini',
        offline: 'local-synthesis-v1'
      }
    }
  };

  // DOM Elements
  const projectSelect = document.getElementById('projectSelect');
  const sidebarProjectTitle = document.getElementById('sidebarProjectTitle');
  const sidebarProjectDesc = document.getElementById('sidebarProjectDesc');
  const statDocCount = document.getElementById('statDocCount');
  const statChunkCount = document.getElementById('statChunkCount');
  const statPageCount = document.getElementById('statPageCount');
  const documentsContainer = document.getElementById('documentsContainer');
  const workspaceFilesContainer = document.getElementById('workspaceFilesContainer');
  const uploadDropzone = document.getElementById('uploadDropzone');
  const pdfFileInput = document.getElementById('pdfFileInput');
  const messagesList = document.getElementById('messagesList');
  const welcomeHero = document.getElementById('welcomeHero');
  const chatInput = document.getElementById('chatInput');
  const sendBtn = document.getElementById('sendBtn');
  const suggestedQuestions = document.getElementById('suggestedQuestions');
  const headerProviderLabel = document.getElementById('headerProviderLabel');
  const activeProviderBadge = document.getElementById('activeProviderBadge');

  // Modals
  const newProjectModal = document.getElementById('newProjectModal');
  const settingsModal = document.getElementById('settingsModal');
  const chunksModal = document.getElementById('chunksModal');
  const citationDetailModal = document.getElementById('citationDetailModal');

  // Initialization
  async function init() {
    setupEventListeners();
    updateProviderBadgeUI();
    await fetchProviders();
    await fetchWorkspaceFiles();
    await fetchProjects();
  }

  // API Calls
  async function fetchProviders() {
    try {
      const res = await fetch('/api/config/providers');
      const data = await res.json();
      state.providers = data.providers;
      populateSettingsModal();
    } catch (e) {
      console.error('Failed to load providers:', e);
    }
  }

  async function fetchWorkspaceFiles() {
    try {
      const res = await fetch('/api/workspace_files');
      const data = await res.json();
      state.workspaceFiles = data.workspace_pdfs || [];
      renderWorkspaceQuickButtons();
    } catch (e) {
      console.error('Failed to load workspace files:', e);
    }
  }

  async function fetchProjects() {
    try {
      const res = await fetch('/api/projects');
      const projects = await res.json();
      state.projects = projects;
      renderProjectSelect();

      if (projects.length > 0) {
        // Load first project or active project
        const targetId = state.currentProjectId || projects[0].id;
        await loadProject(targetId);
      } else {
        // Auto-create starter project for convenience
        await autoCreateStarterProject();
      }
    } catch (e) {
      console.error('Failed to load projects:', e);
      showToast('Error loading projects list', 'error');
    }
  }

  async function autoCreateStarterProject() {
    try {
      showToast('Setting up starter workspace project...', 'info');
      const res = await fetch('/api/projects', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: 'Human Nutrition Study',
          description: 'RAG project based on Human-Nutrition-2020-Edition textbook'
        })
      });
      const newProj = await res.json();
      state.projects = [newProj];
      renderProjectSelect();
      await loadProject(newProj.id);

      // Auto-attach workspace PDF if exists
      if (state.workspaceFiles.length > 0) {
        const file = state.workspaceFiles[0];
        await quickAttachWorkspaceFile(newProj.id, file.filename, 1, 50);
      }
    } catch (e) {
      console.error('Error creating starter project:', e);
    }
  }

  async function loadProject(projectId) {
    state.currentProjectId = projectId;
    projectSelect.value = projectId;

    try {
      const res = await fetch(`/api/projects/${projectId}`);
      if (!res.ok) throw new Error('Project not found');
      const project = await res.json();
      state.currentProject = project;

      renderProjectSidebar(project);
      renderChatHistory(project.chat_history || []);
      renderSuggestedQuestions(project);
    } catch (e) {
      console.error('Error loading project details:', e);
      showToast('Failed to load project', 'error');
    }
  }

  // Render Functions
  function renderProjectSelect() {
    projectSelect.innerHTML = '';
    if (state.projects.length === 0) {
      projectSelect.innerHTML = '<option value="" disabled>No projects</option>';
      return;
    }
    state.projects.forEach(p => {
      const opt = document.createElement('option');
      opt.value = p.id;
      opt.textContent = `${p.name} (${p.document_count || 0} docs)`;
      if (p.id === state.currentProjectId) opt.selected = true;
      projectSelect.appendChild(opt);
    });
  }

  function renderProjectSidebar(proj) {
    sidebarProjectTitle.textContent = proj.name;
    sidebarProjectDesc.textContent = proj.description || 'No description provided.';
    statDocCount.textContent = (proj.documents || []).length;
    statChunkCount.textContent = proj.total_chunks || 0;
    statPageCount.textContent = proj.total_pages || 0;

    // Render documents list
    documentsContainer.innerHTML = '';
    const docs = proj.documents || [];
    if (docs.length === 0) {
      documentsContainer.innerHTML = `
        <div style="font-size: 0.8rem; color: var(--text-muted); text-align: center; padding: 20px 0;">
          No documents uploaded yet.<br>Drop a PDF above to begin.
        </div>
      `;
      return;
    }

    docs.forEach(doc => {
      const card = document.createElement('div');
      card.className = 'doc-item-card';
      const sizeMb = (doc.file_size / (1024 * 1024)).toFixed(1);
      card.innerHTML = `
        <div class="doc-icon">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
        </div>
        <div class="doc-info">
          <div class="doc-name" title="${escapeHtml(doc.filename)}">${escapeHtml(doc.filename)}</div>
          <div class="doc-meta">
            <span>${doc.total_pages} pages (${doc.indexed_start_page}-${doc.indexed_end_page} indexed)</span>
            <span>•</span>
            <span>${sizeMb} MB</span>
          </div>
          <div style="margin-top: 5px;">
            <span class="doc-badge">${doc.chunk_count} chunks indexed</span>
          </div>
        </div>
        <button class="doc-delete-btn" title="Remove ${escapeHtml(doc.filename)}" data-doc-id="${doc.doc_id}">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
        </button>
      `;

      const removeBtn = card.querySelector('.doc-delete-btn');
      removeBtn.addEventListener('click', async (e) => {
        e.stopPropagation();
        if (!confirm(`Are you sure you want to remove "${doc.filename}" from this project?\n\nIts indexed chunks will be deleted from RAG search, and the conversation chat will be cleared.`)) return;

        try {
          removeBtn.disabled = true;
          const res = await fetch(`/api/projects/${state.currentProjectId}/documents/${doc.doc_id}`, {
            method: 'DELETE'
          });
          if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || 'Failed to remove file');
          }
          messagesList.innerHTML = '';
          if (welcomeHero) welcomeHero.style.display = 'none';
          showToast(`File "${doc.filename}" removed and chat cleared`, 'success');
          await fetchProjects();
          await loadProject(state.currentProjectId);
        } catch (err) {
          showToast(err.message || 'Error removing file', 'error');
          removeBtn.disabled = false;
        }
      });

      documentsContainer.appendChild(card);
    });
  }

  function renderWorkspaceQuickButtons() {
    workspaceFilesContainer.innerHTML = '';
    if (state.workspaceFiles.length === 0) return;

    state.workspaceFiles.forEach(file => {
      const btn = document.createElement('button');
      btn.className = 'quick-attach-btn';
      btn.innerHTML = `
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>
        <span>Attach <strong>${escapeHtml(file.filename)}</strong></span>
      `;
      btn.addEventListener('click', async () => {
        if (!state.currentProjectId) {
          showToast('Please select or create a project first', 'error');
          return;
        }
        await quickAttachWorkspaceFile(state.currentProjectId, file.filename, 1, 50);
      });
      workspaceFilesContainer.appendChild(btn);
    });
  }

  function renderSuggestedQuestions(project) {
    if (suggestedQuestions) suggestedQuestions.innerHTML = '';
  }

  function renderChatHistory(history) {
    messagesList.innerHTML = '';
    if (welcomeHero) welcomeHero.style.display = 'none';
    if (history.length === 0) {
      return;
    }

    if (welcomeHero) welcomeHero.style.display = 'none';
    history.forEach(item => {
      appendMessageToUI('user', item.user, null, null, item.timestamp, item.id);
      appendMessageToUI('assistant', item.assistant, item.citations, { provider: item.provider, model: item.model }, item.timestamp, item.id);
    });
    scrollChatToBottom();
  }

  function appendMessageToUI(role, text, citations = null, meta = null, timestamp = null, msgId = null) {
    if (welcomeHero) welcomeHero.style.display = 'none';

    const row = document.createElement('div');
    row.className = `message-row ${role}`;
    if (msgId) row.setAttribute('data-msg-id', msgId);

    const timeStr = timestamp ? new Date(timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    const authorName = role === 'user' ? 'You' : 'DocuRAG Assistant';
    const avatarContent = role === 'user' ? 'U' : 'AI';

    let metaBadge = '';
    if (role === 'assistant' && meta && meta.provider) {
      metaBadge = `<span class="message-provider-badge">${escapeHtml(meta.provider.toUpperCase())} ${meta.model ? `(${escapeHtml(meta.model)})` : ''}</span>`;
    }

    let citationsHtml = '';
    if (citations && citations.length > 0) {
      let cards = citations.map((c, i) => {
        const scorePct = Math.round((c.score || 0.5) * 100);
        return `
          <div class="citation-card" data-citation-idx="${i}">
            <div class="citation-card-top">
              <span class="citation-page-badge">Page ${c.page_number || c.page || '?'}</span>
              <span class="citation-score-badge">${scorePct}% match</span>
            </div>
            <div class="citation-snippet">${escapeHtml(c.text || c.summary || '')}</div>
          </div>
        `;
      }).join('');

      citationsHtml = `
        <div class="citations-wrapper">
          <div class="citations-header">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
            <span>Verified Sources & Citations (${citations.length})</span>
          </div>
          <div class="citations-cards-grid">${cards}</div>
        </div>
      `;
    }

    row.innerHTML = `
      <div class="message-avatar">${avatarContent}</div>
      <div class="message-bubble-wrapper">
        <div class="message-header-meta">
          <span class="message-author">${authorName}</span>
          <span class="message-time">${timeStr}</span>
          ${metaBadge}
          <div class="message-actions">
            <button class="msg-action-btn msg-copy-btn" title="Copy text">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
              <span>Copy</span>
            </button>
            <button class="msg-action-btn delete-btn msg-delete-btn" title="Delete message">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
              <span>Delete</span>
            </button>
          </div>
        </div>
        <div class="message-content">
          ${formatMarkdown(text)}
          ${citationsHtml}
        </div>
      </div>
    `;

    // Copy text handler
    const copyBtn = row.querySelector('.msg-copy-btn');
    if (copyBtn) {
      copyBtn.addEventListener('click', async () => {
        try {
          await navigator.clipboard.writeText(text);
          copyBtn.classList.add('copied');
          copyBtn.innerHTML = `
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#34d399" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>
            <span style="color:#34d399">Copied!</span>
          `;
          showToast('Text copied to clipboard', 'success');
          setTimeout(() => {
            copyBtn.classList.remove('copied');
            copyBtn.innerHTML = `
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
              <span>Copy</span>
            `;
          }, 2000);
        } catch (e) {
          showToast('Failed to copy text', 'error');
        }
      });
    }

    // Delete message handler
    const deleteBtn = row.querySelector('.msg-delete-btn');
    if (deleteBtn) {
      deleteBtn.addEventListener('click', async () => {
        if (!confirm('Are you sure you want to delete this message?')) return;
        row.style.transition = 'all 0.25s ease-out';
        row.style.opacity = '0';
        row.style.transform = 'translateY(6px)';
        setTimeout(() => row.remove(), 250);

        if (msgId && state.currentProjectId) {
          try {
            await fetch(`/api/projects/${state.currentProjectId}/chat/${msgId}`, { method: 'DELETE' });
          } catch (e) {
            console.error('Error deleting chat message from backend:', e);
          }
        }
        showToast('Message deleted', 'info');
      });
    }

    // Add click listeners to citation cards
    if (citations && citations.length > 0) {
      const cards = row.querySelectorAll('.citation-card');
      cards.forEach(card => {
        card.addEventListener('click', () => {
          const idx = parseInt(card.getAttribute('data-citation-idx'), 10);
          showCitationDetailModal(citations[idx]);
        });
      });
    }

    messagesList.appendChild(row);
    scrollChatToBottom();
  }

  function appendThinkingMessage() {
    const row = document.createElement('div');
    row.className = 'message-row assistant';
    row.id = 'thinkingMessageRow';
    row.innerHTML = `
      <div class="message-avatar">AI</div>
      <div class="message-bubble-wrapper">
        <div class="message-header-meta">
          <span class="message-author">DocuRAG Assistant</span>
          <span class="message-time">Searching context...</span>
        </div>
        <div class="message-content" style="display: flex; align-items: center; gap: 12px; padding: 14px 20px;">
          <div class="spinner"></div>
          <span style="color: var(--text-secondary); font-size: 0.88rem;">Retrieving passages & synthesizing answer...</span>
        </div>
      </div>
    `;
    messagesList.appendChild(row);
    scrollChatToBottom();
  }

  function removeThinkingMessage() {
    const el = document.getElementById('thinkingMessageRow');
    if (el) el.remove();
  }

  function scrollChatToBottom() {
    const chatContainer = document.getElementById('chatContainer');
    chatContainer.scrollTop = chatContainer.scrollHeight;
  }

  // Question & Query Handler
  async function handleSendMessage() {
    const query = chatInput.value.trim();
    if (!query) return;

    if (!state.currentProjectId) {
      showToast('Please select or create a project first', 'error');
      return;
    }

    if (!state.currentProject || (state.currentProject.total_chunks || 0) === 0) {
      showToast('Please upload or attach a PDF to this project before querying.', 'error');
      return;
    }

    // Append user message immediately
    appendMessageToUI('user', query);
    chatInput.value = '';
    chatInput.style.height = 'auto';
    const cInputBtn = document.getElementById('copyInputBtn');
    const clrInputBtn = document.getElementById('clearInputBtn');
    if (cInputBtn) cInputBtn.style.display = 'none';
    if (clrInputBtn) clrInputBtn.style.display = 'none';

    sendBtn.disabled = true;
    appendThinkingMessage();

    const activeProvider = state.settings.provider;
    const activeModel = state.settings.models[activeProvider];
    const apiKey = state.settings.keys[activeProvider] || '';

    try {
      const res = await fetch(`/api/projects/${state.currentProjectId}/query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: query,
          top_k: state.settings.topK,
          provider: activeProvider,
          model: activeModel,
          api_key: apiKey
        })
      });

      removeThinkingMessage();

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Failed to generate answer');
      }

      const data = await res.json();

      let answerText = data.answer;
      if (data.notice) {
        answerText += `\n\n> ℹ️ *${data.notice}*`;
      }

      appendMessageToUI('assistant', answerText, data.citations, {
        provider: data.provider || activeProvider,
        model: data.model || activeModel
      });

      // Refresh project metadata
      await loadProject(state.currentProjectId);

    } catch (e) {
      removeThinkingMessage();
      console.error('Error during query:', e);
      appendMessageToUI('assistant', `⚠️ **Error querying project:** ${escapeHtml(e.message)}`);
      showToast('Query error: ' + e.message, 'error');
    } finally {
      sendBtn.disabled = false;
      chatInput.focus();
    }
  }

  // Upload Handlers
  async function handleFileUpload(file) {
    if (!state.currentProjectId) {
      showToast('Please create or select a project first', 'error');
      return;
    }

    if (!file.name.toLowerCase().endsWith('.pdf')) {
      showToast('Only .pdf files are supported', 'error');
      return;
    }

    const formData = new FormData();
    formData.append('file', file);
    formData.append('start_page', 1);
    formData.append('end_page', 100); // Index first 100 pages by default

    showToast(`Uploading and indexing ${file.name}...`, 'info');

    try {
      const res = await fetch(`/api/projects/${state.currentProjectId}/upload`, {
        method: 'POST',
        body: formData
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Upload failed');
      }

      const data = await res.json();
      showToast(`Indexed ${data.chunks_created} chunks from ${file.name}!`, 'success');
      await loadProject(state.currentProjectId);
    } catch (e) {
      console.error('Error uploading file:', e);
      showToast(`Upload failed: ${e.message}`, 'error');
    }
  }

  async function quickAttachWorkspaceFile(projectId, filename, startPage = 1, endPage = 50) {
    showToast(`Indexing ${filename} (pages ${startPage}–${endPage})...`, 'info');
    try {
      const res = await fetch(`/api/projects/${projectId}/quick_attach_local`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          filename: filename,
          start_page: startPage,
          end_page: endPage
        })
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Quick attach failed');
      }

      const data = await res.json();
      showToast(`Successfully indexed ${data.chunks_created} chunks from ${filename}!`, 'success');
      await loadProject(projectId);
    } catch (e) {
      console.error('Quick attach error:', e);
      showToast(`Error: ${e.message}`, 'error');
    }
  }

  // Chunks Explorer Modal
  async function openChunksExplorer(search = '') {
    if (!state.currentProjectId) return;
    const container = document.getElementById('chunksListContainer');
    container.innerHTML = '<div style="text-align: center; padding: 20px;"><div class="spinner" style="margin: 0 auto 10px;"></div>Loading chunks...</div>';
    chunksModal.classList.add('active');

    try {
      const url = `/api/projects/${state.currentProjectId}/chunks${search ? `?search=${encodeURIComponent(search)}` : ''}`;
      const res = await fetch(url);
      const data = await res.json();

      container.innerHTML = '';
      if (!data.chunks || data.chunks.length === 0) {
        container.innerHTML = '<div style="text-align:center; color: var(--text-muted); padding: 20px;">No chunks matched your query.</div>';
        return;
      }

      data.chunks.forEach(chunk => {
        const item = document.createElement('div');
        item.style.cssText = 'background: rgba(255,255,255,0.03); border: 1px solid var(--border-subtle); border-radius: var(--radius-sm); padding: 12px;';
        item.innerHTML = `
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
            <span class="stat-pill">Page ${chunk.page_number}</span>
            <span style="font-family: var(--font-mono); font-size: 0.72rem; color: var(--text-muted);">${escapeHtml(chunk.id)}</span>
          </div>
          <div style="font-size: 0.85rem; color: #cbd5e1; line-height: 1.5;">${escapeHtml(chunk.text)}</div>
        `;
        container.appendChild(item);
      });
    } catch (e) {
      container.innerHTML = `<div style="color: var(--accent-rose); padding: 20px;">Error loading chunks: ${escapeHtml(e.message)}</div>`;
    }
  }

  function showCitationDetailModal(citation) {
    document.getElementById('citationModalPage').textContent = `Page ${citation.page_number || citation.page || '?'}`;
    const scorePct = Math.round((citation.score || 0.5) * 100);
    document.getElementById('citationModalScore').textContent = `${scorePct}% match`;
    document.getElementById('citationModalDoc').textContent = citation.filename || 'PDF Document';
    document.getElementById('citationModalText').textContent = citation.text || citation.summary || 'No text snippet available.';
    citationDetailModal.classList.add('active');
  }

  // Settings UI Helper
  function populateSettingsModal() {
    const providerSelect = document.getElementById('settingsProviderSelect');
    const modelSelect = document.getElementById('settingsModelSelect');
    const apiKeyInput = document.getElementById('settingsApiKeyInput');
    const topKInput = document.getElementById('settingsTopKInput');
    const topKValue = document.getElementById('topKValue');

    providerSelect.value = state.settings.provider;
    topKInput.value = state.settings.topK;
    topKValue.textContent = state.settings.topK;

    function refreshModelAndKeyUI() {
      const p = providerSelect.value;
      const pInfo = state.providers[p] || {};
      const models = pInfo.models || [];

      modelSelect.innerHTML = '';
      models.forEach(m => {
        const opt = document.createElement('option');
        opt.value = m;
        opt.textContent = m;
        if (m === state.settings.models[p]) opt.selected = true;
        modelSelect.appendChild(opt);
      });

      const apiKeyGroup = document.getElementById('settingsApiKeyGroup');
      if (pInfo.requires_key) {
        apiKeyGroup.style.display = 'flex';
        apiKeyInput.value = state.settings.keys[p] || '';
      } else {
        apiKeyGroup.style.display = 'none';
      }
    }

    providerSelect.addEventListener('change', refreshModelAndKeyUI);
    topKInput.addEventListener('input', () => {
      topKValue.textContent = topKInput.value;
    });

    refreshModelAndKeyUI();
  }

  function updateProviderBadgeUI() {
    const p = state.settings.provider;
    const m = state.settings.models[p] || '';
    if (p === 'offline') {
      headerProviderLabel.textContent = 'Local Offline QA';
    } else {
      headerProviderLabel.textContent = `${p.toUpperCase()} (${m})`;
    }
  }

  // Event Listeners
  function setupEventListeners() {
    // Project selection
    projectSelect.addEventListener('change', (e) => {
      if (e.target.value) {
        loadProject(e.target.value);
      }
    });

    // Send question
    sendBtn.addEventListener('click', handleSendMessage);
    chatInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleSendMessage();
      }
    });

    // Auto-grow textarea & toggle input action buttons
    const copyInputBtn = document.getElementById('copyInputBtn');
    const clearInputBtn = document.getElementById('clearInputBtn');

    function toggleInputBtns() {
      const hasText = chatInput.value.trim().length > 0;
      if (copyInputBtn) copyInputBtn.style.display = hasText ? 'inline-flex' : 'none';
      if (clearInputBtn) clearInputBtn.style.display = hasText ? 'inline-flex' : 'none';
    }

    chatInput.addEventListener('input', () => {
      chatInput.style.height = 'auto';
      chatInput.style.height = Math.min(chatInput.scrollHeight, 150) + 'px';
      toggleInputBtns();
    });

    if (copyInputBtn) {
      copyInputBtn.addEventListener('click', async () => {
        const val = chatInput.value.trim();
        if (!val) return;
        try {
          await navigator.clipboard.writeText(val);
          showToast('Input text copied to clipboard', 'success');
        } catch (e) {
          showToast('Failed to copy input text', 'error');
        }
      });
    }

    if (clearInputBtn) {
      clearInputBtn.addEventListener('click', () => {
        chatInput.value = '';
        chatInput.style.height = 'auto';
        toggleInputBtns();
        chatInput.focus();
      });
    }



    // Delete project
    document.getElementById('deleteProjectBtn').addEventListener('click', async () => {
      if (!state.currentProjectId) return;
      const proj = state.currentProject;
      if (!confirm(`Are you sure you want to delete project "${proj ? proj.name : ''}"? This will delete all indexed documents in this project.`)) return;

      try {
        await fetch(`/api/projects/${state.currentProjectId}`, { method: 'DELETE' });
        showToast('Project deleted', 'info');
        state.currentProjectId = null;
        await fetchProjects();
      } catch (e) {
        showToast('Failed to delete project', 'error');
      }
    });

    // Open Modals
    document.getElementById('openNewProjectBtn').addEventListener('click', () => {
      newProjectModal.classList.add('active');
    });

    document.getElementById('openSettingsBtn').addEventListener('click', () => {
      populateSettingsModal();
      settingsModal.classList.add('active');
    });

    activeProviderBadge.addEventListener('click', () => {
      populateSettingsModal();
      settingsModal.classList.add('active');
    });

    document.getElementById('browseChunksBtn').addEventListener('click', () => {
      openChunksExplorer();
    });

    document.getElementById('chunkSearchBtn').addEventListener('click', () => {
      const q = document.getElementById('chunkSearchInput').value.trim();
      openChunksExplorer(q);
    });

    // Close Modals
    document.querySelectorAll('.modal-close-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const overlay = e.target.closest('.modal-overlay');
        if (overlay) overlay.classList.remove('active');
      });
    });

    // Save Settings
    document.getElementById('saveSettingsBtn').addEventListener('click', () => {
      const provider = document.getElementById('settingsProviderSelect').value;
      const model = document.getElementById('settingsModelSelect').value;
      const key = document.getElementById('settingsApiKeyInput').value.trim();
      const topK = parseInt(document.getElementById('settingsTopKInput').value, 10);

      state.settings.provider = provider;
      state.settings.models[provider] = model;
      state.settings.keys[provider] = key;
      state.settings.topK = topK;

      localStorage.setItem('rag_provider', provider);
      localStorage.setItem('rag_top_k', topK.toString());
      localStorage.setItem(`rag_model_${provider}`, model);
      if (key) {
        localStorage.setItem(`rag_key_${provider}`, key);
      }

      updateProviderBadgeUI();
      settingsModal.classList.remove('active');
      showToast('Settings saved successfully', 'success');
    });

    // Create New Project Form Submit
    document.getElementById('submitCreateProjectBtn').addEventListener('click', async () => {
      const name = document.getElementById('newProjName').value.trim();
      const desc = document.getElementById('newProjDesc').value.trim();
      const docSource = document.getElementById('newProjDocSource').value;
      const startPage = parseInt(document.getElementById('newProjStartPage').value || '1', 10);
      const endPage = parseInt(document.getElementById('newProjEndPage').value || '50', 10);

      if (!name) {
        showToast('Please enter a project name', 'error');
        return;
      }

      try {
        const res = await fetch('/api/projects', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name, description: desc })
        });

        if (!res.ok) throw new Error('Failed to create project');
        const proj = await res.json();
        newProjectModal.classList.remove('active');
        document.getElementById('newProjName').value = '';
        document.getElementById('newProjDesc').value = '';

        showToast(`Project "${proj.name}" created!`, 'success');
        await fetchProjects();
        await loadProject(proj.id);

        if (docSource === 'workspace_nutrition' && state.workspaceFiles.length > 0) {
          const target = state.workspaceFiles[0].filename;
          await quickAttachWorkspaceFile(proj.id, target, startPage, endPage);
        }
      } catch (e) {
        showToast('Error creating project: ' + e.message, 'error');
      }
    });

    // File Drag & Drop
    uploadDropzone.addEventListener('dragover', (e) => {
      e.preventDefault();
      uploadDropzone.classList.add('dragover');
    });

    uploadDropzone.addEventListener('dragleave', () => {
      uploadDropzone.classList.remove('dragover');
    });

    uploadDropzone.addEventListener('drop', (e) => {
      e.preventDefault();
      uploadDropzone.classList.remove('dragover');
      if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
        handleFileUpload(e.dataTransfer.files[0]);
      }
    });

    pdfFileInput.addEventListener('change', (e) => {
      if (e.target.files && e.target.files.length > 0) {
        handleFileUpload(e.target.files[0]);
      }
    });
  }

  // Toast System
  function showToast(message, type = 'info') {
    const toastContainer = document.getElementById('toastContainer');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;

    let icon = `
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
    `;
    if (type === 'success') {
      icon = `
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>
      `;
    } else if (type === 'error') {
      icon = `
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>
      `;
    }

    toast.innerHTML = `${icon}<span>${escapeHtml(message)}</span>`;
    toastContainer.appendChild(toast);

    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateX(100%)';
      setTimeout(() => toast.remove(), 300);
    }, 4000);
  }

  // Safe Markdown Formatter
  function formatMarkdown(text) {
    if (!text) return '';
    let html = escapeHtml(text);

    // Headers
    html = html.replace(/^### (.*$)/gim, '<h3>$1</h3>');
    html = html.replace(/^## (.*$)/gim, '<h3>$1</h3>');
    html = html.replace(/^# (.*$)/gim, '<h3>$1</h3>');

    // Bold & Italics
    html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    html = html.replace(/\*(.*?)\*/g, '<em>$1</em>');

    // Blockquotes
    html = html.replace(/^\&gt; (.*$)/gim, '<blockquote>$1</blockquote>');

    // Page tags [Page X]
    html = html.replace(/\[Page\s+(\d+)\]/gi, '<span class="citation-page-badge">Page $1</span>');

    // Bullet points
    html = html.replace(/^\- (.*$)/gim, '<li>$1</li>');
    html = html.replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>');

    // Line breaks
    html = html.replace(/\n\n/g, '<p></p>');
    html = html.replace(/\n/g, '<br>');

    return html;
  }

  function escapeHtml(str) {
    if (typeof str !== 'string') return '';
    return str
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  // Start app
  init();
});
