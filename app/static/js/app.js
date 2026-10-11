/**
 * Bulk Certificate Generator - Interactive UI Application
 * Implements Dashboard, Bulk Generation Wizard, Job Status & Progress, and Certificate Management
 */

const API_BASE = '/api/v1';

// Global state
const state = {
  currentView: 'dashboard',
  stats: null,
  jobs: [],
  certificates: [],
  selectedJob: null,
  selectedCertificate: null,
  activeJobFilter: 'all',
  jobSearchQuery: '',
  certSearchQuery: '',
  certStatusFilter: 'all',
  certJobFilter: 'all',
  certPage: 0,
  certPageSize: 10,
  certTotal: 0,
  wizard: {
    step: 1,
    jobData: {
      job_name: '',
      course_name: '',
      completion_date: '',
      issuer_name: 'Global Certification Authority',
      signatory_name: 'Dr. Sarah Mitchell',
      signatory_title: 'Director of Certification',
    },
    recipients: [],
    validRecipients: [],
    invalidRecipients: [],
    activeJobId: null,
    pollInterval: null,
  }
};

// -------------------------------------------------------------
// Authentication System
// -------------------------------------------------------------
const VALID_CREDENTIALS = {
  usernames: ['admin', 'admin@example.com', 'admin@certgenerator.com', 'admin'],
  password: 'admin123',
  userData: {
    name: 'Admin',
    role: 'Administrator',
    email: 'admin@certgenerator.com'
  }
};

function initAuth() {
  const loginScreen = document.getElementById('login-screen');
  const appLayout = document.getElementById('app-layout');
  const loginForm = document.getElementById('login-form');
  const loginError = document.getElementById('login-error');
  const loginErrorText = document.getElementById('login-error-text');
  const btnLogout = document.getElementById('btn-logout');
  const btnFillDemo = document.getElementById('btn-fill-demo');
  const btnTogglePw = document.getElementById('btn-toggle-password');
  const pwInput = document.getElementById('login-password');
  const eyeOpen = document.getElementById('pw-eye-open');
  const eyeClosed = document.getElementById('pw-eye-closed');

  // Check saved session
  const savedUser = localStorage.getItem('cert_auth_user');

  if (savedUser) {
    try {
      let user = JSON.parse(savedUser);
      // Synchronize with current VALID_CREDENTIALS (updates old cached names like 'Fakruddin' to 'Admin')
      user = {
        ...user,
        ...VALID_CREDENTIALS.userData,
        name: VALID_CREDENTIALS.userData.name || 'Admin',
      };
      localStorage.setItem('cert_auth_user', JSON.stringify(user));
      updateUserInterface(user);
      if (loginScreen) loginScreen.style.display = 'none';
      if (appLayout) appLayout.style.display = 'flex';
      initAppModules();
    } catch (e) {
      localStorage.removeItem('cert_auth_user');
      showLogin();
    }
  } else {
    showLogin();
  }

  function showLogin() {
    if (loginScreen) loginScreen.style.display = 'flex';
    if (appLayout) appLayout.style.display = 'none';
  }

  function showApp(user) {
    updateUserInterface(user);
    if (loginScreen) loginScreen.style.display = 'none';
    if (appLayout) appLayout.style.display = 'flex';
    initAppModules();
  }

  function updateUserInterface(user) {
    const userNameEl = document.querySelector('.user-name');
    const userRoleEl = document.querySelector('.user-role');
    const userAvatarEl = document.querySelector('.user-avatar');
    const displayName = (user && user.name) ? user.name : (VALID_CREDENTIALS.userData.name || 'Admin');
    const displayRole = (user && user.role) ? user.role : (VALID_CREDENTIALS.userData.role || 'Administrator');
    if (userNameEl) userNameEl.textContent = displayName;
    if (userRoleEl) userRoleEl.textContent = displayRole;
    if (userAvatarEl) userAvatarEl.textContent = displayName.charAt(0).toUpperCase();
  }

  function initAppModules() {
    initNavigation();
    initBulkWizard();
    initJobStatusFilters();
    initCertFilters();
    loadDashboardData();
  }

  // Auto-fill Demo credentials
  if (btnFillDemo) {
    btnFillDemo.addEventListener('click', () => {
      const uInput = document.getElementById('login-username');
      if (uInput) uInput.value = 'admin';
      if (pwInput) pwInput.value = 'admin123';
      if (loginError) loginError.style.display = 'none';
    });
  }

  // Toggle password visibility
  if (btnTogglePw && pwInput) {
    btnTogglePw.addEventListener('click', () => {
      const isPw = pwInput.type === 'password';
      pwInput.type = isPw ? 'text' : 'password';
      if (eyeOpen) eyeOpen.style.display = isPw ? 'none' : 'block';
      if (eyeClosed) eyeClosed.style.display = isPw ? 'block' : 'none';
    });
  }

  // Handle Login submission
  if (loginForm) {
    loginForm.addEventListener('submit', (e) => {
      e.preventDefault();
      const uInput = document.getElementById('login-username');
      const usernameVal = uInput ? uInput.value.trim().toLowerCase() : '';
      const passwordVal = pwInput ? pwInput.value.trim() : '';

      const isValidUser = VALID_CREDENTIALS.usernames.includes(usernameVal);
      const isValidPw = passwordVal === VALID_CREDENTIALS.password;

      if (isValidUser && isValidPw) {
        if (loginError) loginError.style.display = 'none';
        const userObj = {
          ...VALID_CREDENTIALS.userData,
          username: usernameVal,
          loggedInAt: new Date().toISOString()
        };
        localStorage.setItem('cert_auth_user', JSON.stringify(userObj));
        showApp(userObj);
        showToast('Signed in successfully. Welcome back, admin!', 'success');
      } else {
        if (loginError) {
          loginError.style.display = 'flex';
          if (loginErrorText) loginErrorText.textContent = 'Invalid credentials. Please use admin / admin123.';
        }
      }
    });
  }

  // Handle Logout
  if (btnLogout) {
    btnLogout.addEventListener('click', (e) => {
      e.preventDefault();
      localStorage.removeItem('cert_auth_user');
      showLogin();
      showToast('You have been logged out successfully.', 'info');
      if (loginForm) loginForm.reset();
      if (loginError) loginError.style.display = 'none';
    });
  }
}

// Initialize app when DOM ready
document.addEventListener('DOMContentLoaded', () => {
  initAuth();

  // Set default today date in date input
  const dateInput = document.getElementById('wizard-completion-date');
  if (dateInput) {
    const today = new Date().toISOString().split('T')[0];
    dateInput.value = today;
    state.wizard.jobData.completion_date = today;
  }
});

// Human-friendly Job ID formatter
function formatJobDisplayId(id) {
  if (!id) return '#1';
  const str = String(id).trim();
  if (/^#?JOB-\d+$/i.test(str)) {
    return str.startsWith('#') ? str.toUpperCase() : `#${str.toUpperCase()}`;
  }
  if (/^\d+$/.test(str)) {
    return `#${str}`;
  }
  return `#${str.substring(0, 8)}`;
}

// Toast notification helper
function showToast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  if (!container) return;
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.innerHTML = `<span>${message}</span>`;
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    setTimeout(() => toast.remove(), 300);
  }, 3500);
}

// -------------------------------------------------------------
// Navigation Router
// -------------------------------------------------------------
function initNavigation() {
  const navItems = document.querySelectorAll('.nav-item');
  navItems.forEach(item => {
    item.addEventListener('click', (e) => {
      e.preventDefault();
      const targetView = item.dataset.view;
      if (!targetView) return;
      switchView(targetView);
    });
  });
}

function switchView(viewName) {
  state.currentView = viewName;

  // Update sidebar active class
  document.querySelectorAll('.nav-item').forEach(item => {
    item.classList.toggle('active', item.dataset.view === viewName);
  });

  // Update visible view section
  document.querySelectorAll('.view-section').forEach(sec => {
    sec.classList.remove('active');
  });
  const activeSec = document.getElementById(`view-${viewName}`);
  if (activeSec) activeSec.classList.add('active');

  // Update header titles
  const titleMap = {
    dashboard: { title: 'Dashboard', desc: 'Overview of certificate generation stats and system activity' },
    'bulk-gen': { title: 'Bulk Certificate Generation', desc: 'Upload recipients data and start certificate generation process' },
    'job-status': { title: 'Job Status & Progress', desc: 'Track the progress of your certificate generation jobs' },
    certificates: { title: 'Certificate Management', desc: 'Search, preview and download generated certificates' },
  };

  const info = titleMap[viewName] || { title: 'Dashboard', desc: '' };
  document.getElementById('header-title').textContent = info.title;
  document.getElementById('header-desc').textContent = info.desc;

  // View specific fetch
  if (viewName === 'dashboard') loadDashboardData();
  if (viewName === 'job-status') loadJobStatusData();
  if (viewName === 'certificates') loadCertificatesData();
}

// -------------------------------------------------------------
// View 1: Dashboard
// -------------------------------------------------------------
async function loadDashboardData() {
  try {
    const [statsRes, jobsRes] = await Promise.all([
      fetch(`${API_BASE}/jobs/stats/overview`),
      fetch(`${API_BASE}/jobs?limit=5&skip=0`),
    ]);

    if (statsRes.ok) {
      state.stats = await statsRes.json();
      renderDashboardStats(state.stats);
    }

    if (jobsRes.ok) {
      const data = await jobsRes.json();
      state.jobs = data.jobs || [];
      renderLatestJobs(state.jobs);
    }
  } catch (err) {
    console.error('Failed to load dashboard data:', err);
  }
}

function renderDashboardStats(stats) {
  document.getElementById('stat-total-jobs').textContent = stats.total_jobs.toLocaleString();
  document.getElementById('stat-total-certs').textContent = stats.total_certificates.toLocaleString();
  document.getElementById('stat-failed-certs').textContent = stats.failed_certificates.toLocaleString();
  document.getElementById('stat-issued-certs').textContent = stats.successful_certificates.toLocaleString();

  // Success rate subtitle
  const issuedRate = stats.total_certificates > 0
    ? Math.round((stats.successful_certificates / stats.total_certificates) * 100)
    : 100;
  document.getElementById('stat-rate-text').textContent = `${issuedRate}% success rate`;

  // Donut Chart calculation
  const b = stats.status_breakdown || { completed: 0, partially_completed: 0, processing: 0, queued: 0, failed: 0 };
  const total = stats.total_jobs || 1;
  const compPct = Math.round(((b.completed || 0) / total) * 100) || 0;
  const partPct = Math.round(((b.partially_completed || 0) / total) * 100) || 0;
  const procPct = Math.round(((b.processing || 0) / total) * 100) || 0;
  const qPct = Math.round(((b.queued || 0) / total) * 100) || 0;
  const failPct = Math.max(0, 100 - compPct - partPct - procPct - qPct);

  document.getElementById('donut-center-total').textContent = stats.total_jobs;
  document.getElementById('legend-completed-count').textContent = b.completed || 0;
  document.getElementById('legend-completed-pct').textContent = `(${compPct}%)`;
  const legPartCount = document.getElementById('legend-partial-count');
  if (legPartCount) {
    legPartCount.textContent = b.partially_completed || 0;
    const legPartPct = document.getElementById('legend-partial-pct');
    if (legPartPct) legPartPct.textContent = `(${partPct}%)`;
  }
  document.getElementById('legend-failed-count').textContent = b.failed || 0;
  document.getElementById('legend-failed-pct').textContent = `(${failPct}%)`;
  document.getElementById('legend-processing-count').textContent = b.processing || 0;
  document.getElementById('legend-processing-pct').textContent = `(${procPct}%)`;
  document.getElementById('legend-queued-count').textContent = b.queued || 0;
  document.getElementById('legend-queued-pct').textContent = `(${qPct}%)`;

  // Update SVG donut stroke dashes
  const circumference = 2 * Math.PI * 50; // ~314.15
  const compDash = (compPct / 100) * circumference;
  const partDash = (partPct / 100) * circumference;
  const procDash = (procPct / 100) * circumference;
  const qDash = (qPct / 100) * circumference;
  const failDash = (failPct / 100) * circumference;

  const circleComp = document.getElementById('donut-circle-completed');
  const circleProc = document.getElementById('donut-circle-processing');
  const circleQueued = document.getElementById('donut-circle-queued');
  const circleFail = document.getElementById('donut-circle-failed');

  if (circleComp) circleComp.setAttribute('stroke-dasharray', `${compDash} ${circumference}`);
  if (circleProc) {
    circleProc.setAttribute('stroke-dasharray', `${procDash} ${circumference}`);
    circleProc.setAttribute('stroke-dashoffset', `-${compDash}`);
  }
  if (circleQueued) {
    circleQueued.setAttribute('stroke-dasharray', `${qDash} ${circumference}`);
    circleQueued.setAttribute('stroke-dashoffset', `-${compDash + procDash}`);
  }
  if (circleFail) {
    circleFail.setAttribute('stroke-dasharray', `${failDash + partDash} ${circumference}`);
    circleFail.setAttribute('stroke-dashoffset', `-${compDash + procDash + qDash}`);
  }

  // Activity list
  const activityList = document.getElementById('recent-activity-list');
  activityList.innerHTML = '';
  if (!stats.recent_activity || stats.recent_activity.length === 0) {
    activityList.innerHTML = '<p style="color:var(--text-muted);font-size:13px;">No recent job activity recorded.</p>';
  } else {
    stats.recent_activity.forEach(item => {
      const statusClass = (item.status || 'completed').toLowerCase();
      const timeStr = item.created_at ? formatTimeAgo(new Date(item.created_at)) : 'just now';
      const el = document.createElement('div');
      el.className = 'activity-item';
      el.innerHTML = `
        <div class="activity-dot ${statusClass}"></div>
        <div class="activity-content">
          <div class="activity-title">${escapeHtml(item.title)}</div>
          <div class="activity-time">${item.status} • ${timeStr} • ${item.success}/${item.total} certs</div>
        </div>
      `;
      activityList.appendChild(el);
    });
  }
}

function renderLatestJobs(jobs) {
  const tbody = document.getElementById('latest-jobs-tbody');
  tbody.innerHTML = '';
  if (jobs.length === 0) {
    tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;padding:24px;color:var(--text-muted);">No generation jobs found yet. Click Bulk Generation to create one.</td></tr>';
    return;
  }

  jobs.forEach(j => {
    const tr = document.createElement('tr');
    const statusClass = (j.status || 'pending').toLowerCase();
    const createdStr = j.created_at ? new Date(j.created_at).toLocaleDateString() + ' ' + new Date(j.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : 'N/A';

    tr.innerHTML = `
      <td><code>${formatJobDisplayId(j.id)}</code></td>
      <td style="font-weight:600;">${escapeHtml(j.title || j.job_name)}</td>
      <td>${j.total_records || j.total_recipients || 0}</td>
      <td style="color:var(--success);font-weight:600;">${j.successful_records || j.successful_count || 0}</td>
      <td style="color:${(j.failed_records > 0) ? 'var(--danger)' : 'var(--text-muted)'};font-weight:600;">${j.failed_records || j.failed_count || 0}</td>
      <td><span class="badge ${statusClass}">${j.status}</span></td>
      <td style="color:var(--text-muted);font-size:12px;">${createdStr}</td>
      <td>
        <button class="btn btn-secondary btn-sm" onclick="viewJobInDetail('${j.id}')">View</button>
      </td>
    `;
    tbody.appendChild(tr);
  });
}

// -------------------------------------------------------------
// View 2: Bulk Certificate Generation Wizard
// -------------------------------------------------------------
function initBulkWizard() {
  // Inputs binding
  const jobNameInput = document.getElementById('wizard-job-name');
  const courseNameInput = document.getElementById('wizard-course-name');
  const dateInput = document.getElementById('wizard-completion-date');

  if (jobNameInput) {
    jobNameInput.addEventListener('input', (e) => {
      state.wizard.jobData.job_name = e.target.value;
      if (!courseNameInput.value) courseNameInput.value = e.target.value;
      state.wizard.jobData.course_name = courseNameInput.value;
    });
  }
  if (courseNameInput) {
    courseNameInput.addEventListener('input', (e) => state.wizard.jobData.course_name = e.target.value);
  }
  if (dateInput) {
    dateInput.addEventListener('input', (e) => state.wizard.jobData.completion_date = e.target.value);
  }

  // Dropzone file handling
  const dropzone = document.getElementById('csv-dropzone');
  const fileInput = document.getElementById('csv-file-input');

  if (dropzone && fileInput) {
    dropzone.addEventListener('click', () => fileInput.click());
    dropzone.addEventListener('dragover', (e) => {
      e.preventDefault();
      dropzone.classList.add('dragover');
    });
    dropzone.addEventListener('dragleave', () => dropzone.classList.remove('dragover'));
    dropzone.addEventListener('drop', (e) => {
      e.preventDefault();
      dropzone.classList.remove('dragover');
      if (e.dataTransfer.files.length > 0) {
        handleCsvFile(e.dataTransfer.files[0]);
      }
    });

    fileInput.addEventListener('change', (e) => {
      if (e.target.files.length > 0) {
        handleCsvFile(e.target.files[0]);
      }
    });
  }

  // Sample CSV generator button
  const downloadSampleBtn = document.getElementById('btn-download-sample-csv');
  if (downloadSampleBtn) {
    downloadSampleBtn.addEventListener('click', downloadSampleCsv);
  }

  // Load sample data / preset buttons
  const loadSampleBtn = document.getElementById('btn-load-sample-data');
  if (loadSampleBtn) {
    loadSampleBtn.addEventListener('click', loadSampleData);
  }

  const btnPresetAllPass = document.getElementById('btn-preset-all-pass');
  if (btnPresetAllPass) {
    btnPresetAllPass.addEventListener('click', loadAllPassPreset);
  }

  const btnPresetSomeFail = document.getElementById('btn-preset-some-fail');
  if (btnPresetSomeFail) {
    btnPresetSomeFail.addEventListener('click', loadSomeFailedPreset);
  }

  const btnPresetAllFail = document.getElementById('btn-preset-all-fail');
  if (btnPresetAllFail) {
    btnPresetAllFail.addEventListener('click', loadAllFailedPreset);
  }

  // Wizard Navigation
  const btnNextReview = document.getElementById('btn-next-review');
  if (btnNextReview) {
    btnNextReview.addEventListener('click', goToReviewStep);
  }

  const btnBackStep1 = document.getElementById('btn-back-step1');
  if (btnBackStep1) {
    btnBackStep1.addEventListener('click', () => setWizardStep(1));
  }

  const btnStartGeneration = document.getElementById('btn-start-generation');
  if (btnStartGeneration) {
    btnStartGeneration.addEventListener('click', startBulkJobGeneration);
  }

  const btnResetWizard = document.getElementById('btn-reset-wizard');
  if (btnResetWizard) {
    btnResetWizard.addEventListener('click', resetBulkWizard);
  }
}

function handleCsvFile(file) {
  if (!file.name.endsWith('.csv')) {
    showToast('Please upload a valid .csv file', 'error');
    return;
  }

  const reader = new FileReader();
  reader.onload = (e) => {
    const text = e.target.result;
    parseCsvContent(text, file.name);
  };
  reader.readAsText(file);
}

function parseCsvContent(csvText, filename = 'recipients.csv') {
  const lines = csvText.split(/\r?\n/).map(l => l.trim()).filter(l => l.length > 0);
  if (lines.length < 2) {
    showToast('CSV file is empty or missing data rows', 'error');
    return;
  }

  const headers = lines[0].split(',').map(h => h.trim().toLowerCase().replace(/['"]/g, ''));
  const nameIdx = headers.indexOf('name') !== -1 ? headers.indexOf('name') : headers.indexOf('recipient_name');
  const emailIdx = headers.indexOf('email') !== -1 ? headers.indexOf('email') : headers.indexOf('recipient_email');

  if (nameIdx === -1 || emailIdx === -1) {
    showToast('CSV must include "name" and "email" columns', 'error');
    return;
  }

  const recipients = [];
  for (let i = 1; i < lines.length; i++) {
    const parts = splitCsvLine(lines[i]);
    const name = parts[nameIdx] ? parts[nameIdx].trim() : '';
    const email = parts[emailIdx] ? parts[emailIdx].trim() : '';

    // Extra fields
    const extra = {};
    headers.forEach((h, idx) => {
      if (idx !== nameIdx && idx !== emailIdx && parts[idx]) {
        extra[h] = parts[idx].trim();
      }
    });

    recipients.push({ name, email, extra_data: Object.keys(extra).length > 0 ? extra : null });
  }

  state.wizard.recipients = recipients;

  // Show file indicator
  const dropzoneTitle = document.querySelector('.dropzone-title');
  if (dropzoneTitle) {
    dropzoneTitle.textContent = `✓ ${filename} loaded (${recipients.length} recipients)`;
    dropzoneTitle.style.color = 'var(--success)';
  }

  showToast(`Loaded ${recipients.length} recipients from ${filename}`, 'success');
}

function splitCsvLine(line) {
  const parts = [];
  let current = '';
  let inQuotes = false;
  for (let i = 0; i < line.length; i++) {
    const char = line[i];
    if (char === '"' || char === "'") {
      inQuotes = !inQuotes;
    } else if (char === ',' && !inQuotes) {
      parts.push(current);
      current = '';
    } else {
      current += char;
    }
  }
  parts.push(current);
  return parts.map(p => p.replace(/^["']|["']$/g, '').trim());
}

function loadSampleData() {
  document.getElementById('wizard-job-name').value = 'Python Training Program';
  document.getElementById('wizard-course-name').value = 'Python Programming & Architecture';
  state.wizard.jobData.job_name = 'Python Training Program';
  state.wizard.jobData.course_name = 'Python Programming & Architecture';

  const sampleCsv = `name,email,grade,honors
Rahul Sharma,rahul@example.com,A+,Distinction
Priya Verma,priya@example.com,A,Honors
Arjun Patel,arjun.patel@example.com,A+,High Honors
Sneha Mukherjee,sneha.m@example.com,A,Distinction
Vikram Singh,vikram.singh@example.com,B+,Merit`;

  parseCsvContent(sampleCsv, 'sample_recipients.csv');
}

function downloadSampleCsv() {
  const csvContent = `name,email,grade,honors
Rahul Sharma,rahul@example.com,A+,Distinction
Priya Verma,priya@example.com,A,Honors
Arjun Patel,arjun.p@example.com,A+,High Honors
Sneha Mukherjee,sneha.m@example.com,A,Distinction
Vikram Singh,vikram.s@example.com,B+,Merit
Ananya Sen,ananya.s@example.com,A+,Distinction`;

  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'sample_recipients_template.csv';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
  showToast('Sample CSV template downloaded', 'success');
}

function loadAllPassPreset() {
  document.getElementById('wizard-job-name').value = 'Python Full Stack Bootcamp [TEST CASE: ALL PASS]';
  document.getElementById('wizard-course-name').value = 'Python Full Stack Development';
  document.getElementById('wizard-completion-date').value = '2026-10-20';
  state.wizard.recipients = [
    { name: 'Aarav Sharma', email: 'aarav.sharma@example.com', extra_data: { grade: 'A+' } },
    { name: 'Ananya Iyer', email: 'ananya.iyer@example.com', extra_data: { grade: 'A', honors: 'Distinction' } },
    { name: 'Rohan Verma', email: 'rohan.verma@example.com', extra_data: { grade: 'A' } },
    { name: 'Sneha Nair', email: 'sneha.nair@example.com', extra_data: { grade: 'O', honors: 'First Class' } },
  ];
  updateDropzonePresetStatus(state.wizard.recipients.length, '🟢 Loaded Preset: All Pass (4 recipients)');
  showToast('Loaded Scenario 1: All Certificates Pass (4 recipients)', 'success');
}

function loadSomeFailedPreset() {
  document.getElementById('wizard-job-name').value = 'Cloud & DevOps Masterclass [TEST CASE: SOME FAILED]';
  document.getElementById('wizard-course-name').value = 'DevOps & Kubernetes Engineering';
  document.getElementById('wizard-completion-date').value = '2026-10-22';
  state.wizard.recipients = [
    { name: 'Vikram Malhotra', email: 'vikram.m@example.com', extra_data: { grade: 'A+' } },
    { name: 'Meera Joshi', email: 'meera.j@example.com', extra_data: { grade: 'B+' } },
    { name: 'Kunal Singhania', email: 'kunal.s@example.com', extra_data: { grade: 'A' } },
    {
      name: 'Corrupted Signature Student',
      email: 'corrupted.cert@example.com',
      extra_data: { simulate_failure: true, failure_reason: 'Digital signature verification failed: corrupted recipient signing key' },
    },
    {
      name: 'Invalid Layout Record',
      email: 'invalid.layout@example.com',
      extra_data: { simulate_failure: true, failure_reason: 'Certificate template layout overflow: font metrics mismatch' },
    },
  ];
  updateDropzonePresetStatus(state.wizard.recipients.length, '🟡 Loaded Preset: Some Failed (3 pass, 2 fail)');
  showToast('Loaded Scenario 2: Some Certificates Fail (3 Pass, 2 Fail)', 'warning');
}

function loadAllFailedPreset() {
  document.getElementById('wizard-job-name').value = 'Cybersecurity Penetration Testing [TEST CASE: ALL FAILED]';
  document.getElementById('wizard-course-name').value = 'Offensive Security & Pen-Testing';
  document.getElementById('wizard-completion-date').value = '2026-10-24';
  state.wizard.recipients = [
    {
      name: 'Audit Candidate Alpha',
      email: 'candidate.alpha@example.com',
      extra_data: { simulate_failure: true, failure_reason: 'Organization accreditation token expired on issuer authority' },
    },
    {
      name: 'Audit Candidate Beta',
      email: 'candidate.beta@example.com',
      extra_data: { simulate_failure: true, failure_reason: 'Digital signature certificate authority unreachable (HTTP 503)' },
    },
    {
      name: 'Audit Candidate Gamma',
      email: 'candidate.gamma@example.com',
      extra_data: { simulate_failure: true, failure_reason: 'Compliance verification policy rejected: security clearance mismatch' },
    },
  ];
  updateDropzonePresetStatus(state.wizard.recipients.length, '🔴 Loaded Preset: All Failed (3 fail)');
  showToast('Loaded Scenario 3: All Certificates Fail (3 Failures)', 'error');
}

function updateDropzonePresetStatus(count, label) {
  const dropzoneTitle = document.querySelector('.dropzone-title');
  if (dropzoneTitle) {
    dropzoneTitle.textContent = label || `✓ Loaded ${count} recipients from preset`;
    dropzoneTitle.style.color = 'var(--primary)';
  }
}

function setWizardStep(stepNumber) {
  state.wizard.step = stepNumber;

  // Update Stepper item classes
  document.querySelectorAll('.step-item').forEach(item => {
    const step = parseInt(item.dataset.step);
    item.classList.remove('active', 'completed');
    if (step === stepNumber) item.classList.add('active');
    else if (step < stepNumber) item.classList.add('completed');
  });

  // Toggle step panels
  document.getElementById('wizard-step-1').style.display = (stepNumber === 1) ? 'block' : 'none';
  document.getElementById('wizard-step-2').style.display = (stepNumber === 2) ? 'block' : 'none';
  document.getElementById('wizard-step-3').style.display = (stepNumber === 3) ? 'block' : 'none';
}

function goToReviewStep() {
  const jobName = document.getElementById('wizard-job-name').value.trim();
  const courseName = document.getElementById('wizard-course-name').value.trim();
  const compDate = document.getElementById('wizard-completion-date').value.trim();

  if (!jobName) {
    showToast('Please enter a Job Name', 'error');
    return;
  }
  if (!state.wizard.recipients || state.wizard.recipients.length === 0) {
    showToast('Please upload a CSV file or load sample recipients', 'error');
    return;
  }

  state.wizard.jobData.job_name = jobName;
  state.wizard.jobData.course_name = courseName || jobName;
  state.wizard.jobData.completion_date = compDate;

  // Validate recipients
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  state.wizard.validRecipients = [];
  state.wizard.invalidRecipients = [];

  state.wizard.recipients.forEach((rec, idx) => {
    const nameValid = rec.name && rec.name.trim().length > 0;
    const emailValid = rec.email && emailRegex.test(rec.email.trim());

    if (nameValid && emailValid) {
      state.wizard.validRecipients.push(rec);
    } else {
      let reason = 'Invalid data';
      if (!nameValid && !emailValid) reason = 'Empty name & invalid email';
      else if (!nameValid) reason = 'Missing recipient name';
      else if (!emailValid) reason = 'Malformed email format';
      state.wizard.invalidRecipients.push({ ...rec, reason, index: idx + 1 });
    }
  });

  // Render review counts
  document.getElementById('review-valid-count').textContent = `${state.wizard.validRecipients.length} Valid Recipients`;
  document.getElementById('review-invalid-count').textContent = `${state.wizard.invalidRecipients.length} Invalid Entries`;

  // Render table
  const tbody = document.getElementById('review-table-tbody');
  tbody.innerHTML = '';

  // Show first 15 records in review
  const previewSlice = state.wizard.recipients.slice(0, 15);
  previewSlice.forEach((r, idx) => {
    const isValid = state.wizard.validRecipients.includes(r);
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>#${idx + 1}</td>
      <td style="font-weight:600;">${escapeHtml(r.name || '(Empty)')}</td>
      <td>${escapeHtml(r.email || '(Empty)')}</td>
      <td>${escapeHtml(state.wizard.jobData.course_name)}</td>
      <td>
        <span class="badge ${isValid ? 'success' : 'failed'}">${isValid ? 'Valid' : 'Validation Error'}</span>
      </td>
    `;
    tbody.appendChild(tr);
  });

  if (state.wizard.recipients.length > 15) {
    const tr = document.createElement('tr');
    tr.innerHTML = `<td colspan="5" style="text-align:center;color:var(--text-muted);padding:10px;">... and ${state.wizard.recipients.length - 15} more records</td>`;
    tbody.appendChild(tr);
  }

  setWizardStep(2);
}

async function startBulkJobGeneration() {
  if (state.wizard.validRecipients.length === 0) {
    showToast('Cannot generate job with 0 valid recipients', 'error');
    return;
  }

  const payload = {
    job_name: state.wizard.jobData.job_name,
    title: state.wizard.jobData.job_name,
    course_name: state.wizard.jobData.course_name,
    completion_date: state.wizard.jobData.completion_date,
    event_date: state.wizard.jobData.completion_date,
    issuer_name: state.wizard.jobData.issuer_name,
    signatory_name: state.wizard.jobData.signatory_name,
    signatory_title: state.wizard.jobData.signatory_title,
    recipients: state.wizard.validRecipients,
  };

  try {
    const res = await fetch(`${API_BASE}/certificate-jobs`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail ? JSON.stringify(err.detail) : 'Failed to create bulk job');
    }

    const job = await res.json();
    state.wizard.activeJobId = job.id;
    setWizardStep(3);
    showToast('Job created successfully! Generation underway...', 'success');

    // Begin live polling
    startJobPolling(job.id);
  } catch (err) {
    showToast(err.message, 'error');
  }
}

function startJobPolling(jobId) {
  if (state.wizard.pollInterval) clearInterval(state.wizard.pollInterval);

  state.wizard.pollInterval = setInterval(async () => {
    try {
      const res = await fetch(`${API_BASE}/certificate-jobs/${jobId}`);
      if (!res.ok) return;
      const job = await res.json();
      updateWizardProgress(job);

      if (['COMPLETED', 'PARTIALLY_COMPLETED', 'FAILED'].includes(job.status)) {
        clearInterval(state.wizard.pollInterval);
        state.wizard.pollInterval = null;
        showToast(`Job ${job.status}: ${job.successful_records} certificates generated!`, 'success');
      }
    } catch (e) {
      console.error('Polling error', e);
    }
  }, 1000);
}

function updateWizardProgress(job) {
  const pct = job.progress_percentage || 0;
  document.getElementById('wizard-progress-bar').style.width = `${pct}%`;
  document.getElementById('wizard-progress-pct').textContent = `${pct}%`;
  document.getElementById('wizard-job-status-badge').textContent = job.status;
  document.getElementById('wizard-job-status-badge').className = `badge ${(job.status || 'processing').toLowerCase()}`;
  document.getElementById('wizard-total-count').textContent = job.total_records || job.total_recipients || 0;
  document.getElementById('wizard-success-count').textContent = job.successful_records || job.successful_count || 0;
  document.getElementById('wizard-failed-count').textContent = job.failed_records || job.failed_count || 0;

  const dlBtn = document.getElementById('wizard-download-zip-btn');
  const dlPngBtn = document.getElementById('wizard-download-png-zip-btn');
  if (job.download_all_url || job.download_all_pdf_url) {
    const pdfZipUrl = job.download_all_pdf_url || job.download_all_url;
    const pngZipUrl = job.download_all_png_url || (pdfZipUrl.includes('?') ? pdfZipUrl.replace('format=pdf', 'format=png') : `${pdfZipUrl}?format=png`);
    if (dlBtn) {
      dlBtn.style.display = 'inline-flex';
      dlBtn.onclick = () => window.open(pdfZipUrl, '_blank');
    }
    if (dlPngBtn) {
      dlPngBtn.style.display = 'inline-flex';
      dlPngBtn.onclick = () => window.open(pngZipUrl, '_blank');
    }
  } else {
    if (dlBtn) dlBtn.style.display = 'none';
    if (dlPngBtn) dlPngBtn.style.display = 'none';
  }
}

function resetBulkWizard() {
  if (state.wizard.pollInterval) clearInterval(state.wizard.pollInterval);
  state.wizard.recipients = [];
  state.wizard.validRecipients = [];
  state.wizard.invalidRecipients = [];
  state.wizard.activeJobId = null;
  document.getElementById('wizard-job-name').value = '';
  document.getElementById('wizard-course-name').value = '';
  const dropzoneTitle = document.querySelector('.dropzone-title');
  if (dropzoneTitle) {
    dropzoneTitle.textContent = 'Drag & drop a CSV file here';
    dropzoneTitle.style.color = 'var(--text-primary)';
  }
  setWizardStep(1);
}

// -------------------------------------------------------------
// View 3: Job Status & Progress
// -------------------------------------------------------------
async function loadJobStatusData() {
  try {
    const [jobsRes, statsRes] = await Promise.all([
      fetch(`${API_BASE}/jobs?limit=50&skip=0`),
      fetch(`${API_BASE}/jobs/stats/overview`),
    ]);

    if (jobsRes.ok) {
      const data = await jobsRes.json();
      state.jobs = data.jobs || [];
      renderJobsTable();
    }

    if (statsRes.ok) {
      const stats = await statsRes.json();
      updateStatusFilterPills(stats);
    }
  } catch (err) {
    console.error('Failed to load jobs list:', err);
  }
}

function updateStatusFilterPills(stats) {
  const b = stats.status_breakdown || { completed: 0, partially_completed: 0, processing: 0, queued: 0, failed: 0 };
  const pillTotal = document.getElementById('filter-pill-total');
  const pillComp = document.getElementById('filter-pill-completed');
  const pillPartial = document.getElementById('filter-pill-partial');
  const pillProc = document.getElementById('filter-pill-processing');
  const pillFail = document.getElementById('filter-pill-failed');
  const pillQueue = document.getElementById('filter-pill-queued');

  if (pillTotal) pillTotal.textContent = stats.total_jobs || 0;
  if (pillComp) pillComp.textContent = b.completed || 0;
  if (pillPartial) pillPartial.textContent = b.partially_completed || 0;
  if (pillProc) pillProc.textContent = b.processing || 0;
  if (pillFail) pillFail.textContent = b.failed || 0;
  if (pillQueue) pillQueue.textContent = b.queued || 0;
}

function initJobStatusFilters() {
  // Filter pills
  document.querySelectorAll('.metric-pill').forEach(pill => {
    pill.addEventListener('click', () => {
      document.querySelectorAll('.metric-pill').forEach(p => p.classList.remove('active'));
      pill.classList.add('active');
      state.activeJobFilter = pill.dataset.filter || 'all';
      renderJobsTable();
    });
  });

  // Search input
  const searchInput = document.getElementById('jobs-search-input');
  if (searchInput) {
    searchInput.addEventListener('input', (e) => {
      state.jobSearchQuery = e.target.value.toLowerCase().trim();
      renderJobsTable();
    });
  }

  // Status dropdown filter
  const statusSelect = document.getElementById('jobs-status-select');
  if (statusSelect) {
    statusSelect.addEventListener('change', (e) => {
      state.activeJobFilter = e.target.value;
      renderJobsTable();
    });
  }

  // Refresh button
  const refreshBtn = document.getElementById('jobs-refresh-btn');
  if (refreshBtn) {
    refreshBtn.addEventListener('click', () => {
      loadJobStatusData();
      showToast('Jobs refreshed', 'info');
    });
  }

  // Seed / Run Test Scenarios buttons
  const btnSeedJobs = document.getElementById('btn-seed-test-cases-jobs');
  if (btnSeedJobs) {
    btnSeedJobs.addEventListener('click', triggerSeedTestScenarios);
  }

  const btnSeedDash = document.getElementById('btn-seed-test-cases-dash');
  if (btnSeedDash) {
    btnSeedDash.addEventListener('click', triggerSeedTestScenarios);
  }
}

async function triggerSeedTestScenarios() {
  try {
    showToast('Executing and generating all 3 test case scenarios...', 'info');
    const res = await fetch(`${API_BASE}/jobs/seed-test-scenarios?clear_existing=true`, {
      method: 'POST',
    });
    if (!res.ok) throw new Error('Failed to seed test cases');
    const jobs = await res.json();
    showToast(`Created ${jobs.length} test scenario jobs: 1) All Pass, 2) Some Failed, 3) All Failed`, 'success');
    await loadDashboardData();
    await loadJobStatusData();
    if (state.currentView !== 'job-status') {
      switchView('job-status');
    }
  } catch (err) {
    showToast(err.message, 'error');
  }
}

function renderJobsTable() {
  const tbody = document.getElementById('jobs-table-tbody');
  tbody.innerHTML = '';

  let filtered = state.jobs.slice();

  // Filter by status pill / dropdown
  if (state.activeJobFilter !== 'all') {
    filtered = filtered.filter(j => (j.status || '').toLowerCase() === state.activeJobFilter.toLowerCase());
  }

  // Filter by search query
  if (state.jobSearchQuery) {
    filtered = filtered.filter(j =>
      (j.title || '').toLowerCase().includes(state.jobSearchQuery) ||
      (j.id || '').toLowerCase().includes(state.jobSearchQuery) ||
      formatJobDisplayId(j.id).toLowerCase().includes(state.jobSearchQuery)
    );
  }

  if (filtered.length === 0) {
    tbody.innerHTML = '<tr><td colspan="9" style="text-align:center;padding:32px;color:var(--text-muted);">No jobs matching criteria.</td></tr>';
    return;
  }

  filtered.forEach(j => {
    const tr = document.createElement('tr');
    const statusClass = (j.status || 'pending').toLowerCase();
    const progress = j.progress_percentage || 0;
    const createdStr = j.created_at ? new Date(j.created_at).toLocaleDateString() : 'N/A';

    tr.innerHTML = `
      <td><code>${formatJobDisplayId(j.id)}</code></td>
      <td style="font-weight:600;">${escapeHtml(j.title || j.job_name)}</td>
      <td>${j.total_records || j.total_recipients || 0}</td>
      <td style="color:var(--success);font-weight:600;">${j.successful_records || j.successful_count || 0}</td>
      <td style="color:${(j.failed_records > 0) ? 'var(--danger)' : 'var(--text-muted)'};font-weight:600;">${j.failed_records || j.failed_count || 0}</td>
      <td><span class="badge ${statusClass}">${j.status}</span></td>
      <td style="width:140px;">
        <div style="font-size:11px;font-weight:600;margin-bottom:2px;">${progress}%</div>
        <div class="progress-bar-container">
          <div class="progress-bar-fill" style="width:${progress}%;"></div>
        </div>
      </td>
      <td style="color:var(--text-muted);font-size:12px;">${createdStr}</td>
      <td>
        <div style="display:flex;gap:4px;">
          <button class="btn btn-secondary btn-sm" onclick="viewJobInDetail('${j.id}')">View</button>
          ${j.download_all_url ? `<a href="${j.download_all_pdf_url || j.download_all_url}" target="_blank" class="btn btn-primary btn-sm" title="Download all certificates as PDF ZIP">PDF 📦</a>` : ''}
          ${j.download_all_url ? `<a href="${j.download_all_png_url || (j.download_all_url.includes('?') ? j.download_all_url.replace('format=pdf', 'format=png') : `${j.download_all_url}?format=png`)}" target="_blank" class="btn btn-secondary btn-sm" title="Download all certificates as PNG ZIP">PNG 🖼️</a>` : ''}
        </div>
      </td>
    `;
    tbody.appendChild(tr);
  });
}

async function viewJobInDetail(jobId) {
  try {
    const res = await fetch(`${API_BASE}/certificate-jobs/${jobId}`);
    if (!res.ok) throw new Error('Job details not found');
    const job = await res.json();
    state.selectedJob = job;

    // Switch to job-status view if not already there
    if (state.currentView !== 'job-status') {
      switchView('job-status');
    }

    const drawer = document.getElementById('job-detail-drawer');
    drawer.style.display = 'block';

    document.getElementById('drawer-job-title').textContent = `Job ${formatJobDisplayId(job.id)} - ${job.title}`;
    document.getElementById('drawer-status-badge').textContent = job.status;
    document.getElementById('drawer-status-badge').className = `badge ${(job.status || 'pending').toLowerCase()}`;
    document.getElementById('drawer-total').textContent = job.total_records;
    document.getElementById('drawer-success').textContent = job.successful_records;
    document.getElementById('drawer-failed').textContent = job.failed_records;
    document.getElementById('drawer-progress').textContent = `${job.progress_percentage}%`;
    document.getElementById('drawer-created').textContent = job.created_at ? new Date(job.created_at).toLocaleString() : 'N/A';
    document.getElementById('drawer-completed').textContent = job.completed_at ? new Date(job.completed_at).toLocaleString() : 'In Progress';

    // Download ZIP buttons
    const zipBtn = document.getElementById('drawer-download-zip-btn');
    const zipPngBtn = document.getElementById('drawer-download-png-zip-btn');
    if (job.download_all_url || job.download_all_pdf_url) {
      const pdfZipUrl = job.download_all_pdf_url || job.download_all_url;
      const pngZipUrl = job.download_all_png_url || (pdfZipUrl.includes('?') ? pdfZipUrl.replace('format=pdf', 'format=png') : `${pdfZipUrl}?format=png`);
      if (zipBtn) {
        zipBtn.style.display = 'inline-flex';
        zipBtn.onclick = () => window.open(pdfZipUrl, '_blank');
      }
      if (zipPngBtn) {
        zipPngBtn.style.display = 'inline-flex';
        zipPngBtn.onclick = () => window.open(pngZipUrl, '_blank');
      }
    } else {
      if (zipBtn) zipBtn.style.display = 'none';
      if (zipPngBtn) zipPngBtn.style.display = 'none';
    }

    // Render recipient certificates table inside drawer
    const tbody = document.getElementById('drawer-recipients-tbody');
    tbody.innerHTML = '';
    const certs = job.certificates || [];
    if (certs.length === 0) {
      tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;color:var(--text-muted);padding:18px;">No certificate records yet.</td></tr>';
    } else {
      certs.forEach(c => {
        const tr = document.createElement('tr');
        const stClass = (c.status || 'pending').toLowerCase();
        const pdfUrl = c.download_pdf_url || c.download_url;
        const pngUrl = c.download_png_url || (pdfUrl ? (pdfUrl.includes('?') ? pdfUrl.replace('format=pdf', 'format=png') : `${pdfUrl}?format=png`) : null);
        tr.innerHTML = `
          <td><code>${c.verification_code || c.id.substring(0, 8)}</code></td>
          <td style="font-weight:600;">${escapeHtml(c.recipient_name)}</td>
          <td>${escapeHtml(c.recipient_email)}</td>
          <td><span class="badge ${stClass}">${c.status}</span></td>
          <td style="color:${c.error_message ? 'var(--danger)' : 'var(--text-muted)'};font-size:12px;">${escapeHtml(c.error_message || '—')}</td>
          <td>
            ${c.download_url ? `
              <div style="display:inline-flex;gap:4px;">
                <a href="${pdfUrl}" target="_blank" class="btn btn-primary btn-sm" title="Download PDF Certificate">PDF ↓</a>
                <a href="${pngUrl}" target="_blank" class="btn btn-secondary btn-sm" title="Download PNG Certificate">PNG ↓</a>
              </div>
            ` : '—'}
          </td>
        `;
        tbody.appendChild(tr);
      });
    }

    drawer.scrollIntoView({ behavior: 'smooth' });
  } catch (err) {
    showToast(err.message, 'error');
  }
}

// -------------------------------------------------------------
// View 4: Certificate Management
// -------------------------------------------------------------
async function loadCertificatesData() {
  try {
    let url = `${API_BASE}/certificates?skip=${state.certPage * state.certPageSize}&limit=${state.certPageSize}`;
    if (state.certSearchQuery) url += `&search=${encodeURIComponent(state.certSearchQuery)}`;
    if (state.certStatusFilter !== 'all') url += `&status=${encodeURIComponent(state.certStatusFilter)}`;
    if (state.certJobFilter !== 'all') url += `&job_id=${encodeURIComponent(state.certJobFilter)}`;

    const [certsRes, jobsRes] = await Promise.all([
      fetch(url),
      fetch(`${API_BASE}/jobs?limit=100`),
    ]);

    if (certsRes.ok) {
      const data = await certsRes.json();
      state.certificates = data.certificates || [];
      state.certTotal = data.total || 0;
      renderCertificatesTable();
    }

    if (jobsRes.ok) {
      const jobData = await jobsRes.json();
      populateCertJobDropdown(jobData.jobs || []);
    }
  } catch (err) {
    console.error('Failed to load certificates:', err);
  }
}

function initCertFilters() {
  const searchInput = document.getElementById('cert-search-input');
  if (searchInput) {
    searchInput.addEventListener('input', (e) => {
      state.certSearchQuery = e.target.value.trim();
      state.certPage = 0;
      loadCertificatesData();
    });
  }

  const jobSelect = document.getElementById('cert-job-select');
  if (jobSelect) {
    jobSelect.addEventListener('change', (e) => {
      state.certJobFilter = e.target.value;
      state.certPage = 0;
      loadCertificatesData();
    });
  }

  const statusSelect = document.getElementById('cert-status-select');
  if (statusSelect) {
    statusSelect.addEventListener('change', (e) => {
      state.certStatusFilter = e.target.value;
      state.certPage = 0;
      loadCertificatesData();
    });
  }

  const searchBtn = document.getElementById('cert-search-btn');
  if (searchBtn) {
    searchBtn.addEventListener('click', () => {
      state.certPage = 0;
      loadCertificatesData();
    });
  }
}

function populateCertJobDropdown(jobs) {
  const select = document.getElementById('cert-job-select');
  if (!select) return;
  const currentVal = select.value;
  select.innerHTML = '<option value="all">All Jobs</option>';
  jobs.forEach(j => {
    const opt = document.createElement('option');
    opt.value = j.id;
    opt.textContent = `${j.title} (${formatJobDisplayId(j.id)})`;
    select.appendChild(opt);
  });
  select.value = currentVal;
}

function renderCertificatesTable() {
  const tbody = document.getElementById('certificates-table-tbody');
  tbody.innerHTML = '';

  if (state.certificates.length === 0) {
    tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;padding:32px;color:var(--text-muted);">No certificates found.</td></tr>';
    return;
  }

  state.certificates.forEach((c, idx) => {
    const tr = document.createElement('tr');
    tr.style.cursor = 'pointer';
    tr.onclick = () => selectCertificateForPreview(c);

    const stClass = (c.status || 'pending').toLowerCase();
    const createdStr = c.created_at ? new Date(c.created_at).toLocaleDateString() : 'N/A';

    tr.innerHTML = `
      <td><code>${c.verification_code || c.id.substring(0, 8)}</code></td>
      <td style="font-weight:600;">${escapeHtml(c.recipient_name)}</td>
      <td>${escapeHtml(c.recipient_email)}</td>
      <td>${escapeHtml(c.course_name || 'Certificate Program')}</td>
      <td><span class="badge ${stClass}">${c.status}</span></td>
      <td>
        ${c.download_url ? `
          <div style="display:inline-flex;gap:4px;" onclick="event.stopPropagation()">
            <a href="${c.download_pdf_url || c.download_url}" target="_blank" class="btn btn-primary btn-sm" title="Download PDF Certificate">PDF ↓</a>
            <a href="${c.download_png_url || (c.download_url.includes('?') ? c.download_url.replace('format=pdf', 'format=png') : `${c.download_url}?format=png`)}" target="_blank" class="btn btn-secondary btn-sm" title="Download PNG Certificate">PNG ↓</a>
          </div>
        ` : '—'}
      </td>
      <td style="color:var(--text-muted);font-size:12px;">${createdStr}</td>
    `;
    tbody.appendChild(tr);

    // Auto-select first item for preview if none selected
    if (idx === 0 && !state.selectedCertificate) {
      selectCertificateForPreview(c);
    }
  });

  renderCertPagination();
}

function selectCertificateForPreview(cert) {
  state.selectedCertificate = cert;
  document.getElementById('preview-recipient-name').textContent = cert.recipient_name;
  document.getElementById('preview-course-title').textContent = cert.course_name || 'Certificate of Completion';
  document.getElementById('preview-code').textContent = cert.verification_code || cert.id.substring(0, 10);
  document.getElementById('preview-meta-name').textContent = cert.recipient_name;
  document.getElementById('preview-meta-course').textContent = cert.course_name || 'N/A';
  document.getElementById('preview-meta-date').textContent = cert.created_at ? new Date(cert.created_at).toLocaleDateString() : 'N/A';
  document.getElementById('preview-meta-id').textContent = cert.verification_code || cert.id;

  const dlBtn = document.getElementById('preview-download-btn');
  const dlPngBtn = document.getElementById('preview-download-png-btn');
  if (cert.download_url || cert.download_pdf_url) {
    const pdfUrl = cert.download_pdf_url || cert.download_url;
    const pngUrl = cert.download_png_url || (pdfUrl.includes('?') ? pdfUrl.replace('format=pdf', 'format=png') : `${pdfUrl}?format=png`);
    if (dlBtn) {
      dlBtn.style.display = 'inline-flex';
      dlBtn.onclick = () => window.open(pdfUrl, '_blank');
    }
    if (dlPngBtn) {
      dlPngBtn.style.display = 'inline-flex';
      dlPngBtn.onclick = () => window.open(pngUrl, '_blank');
    }
  } else {
    if (dlBtn) dlBtn.style.display = 'none';
    if (dlPngBtn) dlPngBtn.style.display = 'none';
  }
}

function renderCertPagination() {
  const container = document.getElementById('cert-pagination-controls');
  if (!container) return;
  container.innerHTML = '';

  const totalPages = Math.ceil(state.certTotal / state.certPageSize) || 1;
  document.getElementById('cert-total-label').textContent = `Showing ${state.certificates.length} of ${state.certTotal} certificates`;

  for (let p = 0; p < totalPages; p++) {
    if (p > 5 && p < totalPages - 1 && Math.abs(p - state.certPage) > 2) {
      continue;
    }
    const btn = document.createElement('button');
    btn.className = `page-btn ${p === state.certPage ? 'active' : ''}`;
    btn.textContent = p + 1;
    btn.onclick = () => {
      state.certPage = p;
      loadCertificatesData();
    };
    container.appendChild(btn);
  }
}

// -------------------------------------------------------------
// Utilities
// -------------------------------------------------------------
function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function formatTimeAgo(date) {
  const seconds = Math.floor((new Date() - date) / 1000);
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}
