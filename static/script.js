// ========================================================
// TalentAI - Client Interaction Script
// ========================================================

document.addEventListener("DOMContentLoaded", () => {
    initTabs();
    initDropzones();
    loadStats();
    loadJobsCatalog();
    initForms();
});

// --- Tab Switching ---
function initTabs() {
    const tabs = document.querySelectorAll(".tab-btn");
    const contents = document.querySelectorAll(".tab-content");

    tabs.forEach(tab => {
        tab.addEventListener("click", () => {
            tabs.forEach(t => t.classList.remove("active"));
            contents.forEach(c => c.style.display = "none");

            tab.classList.add("active");
            const targetId = tab.getAttribute("data-tab");
            const targetContent = document.getElementById(targetId);
            if (targetContent) {
                targetContent.style.display = "block";
            }
        });
    });
}

// --- Drag & Drop Files ---
function initDropzones() {
    setupDropzone("resumeDropzone", "resumeFileInput", "resumeFileName");
    setupDropzone("jobDropzone", "jobFileInput", "jobFileName");
}

function setupDropzone(zoneId, inputId, labelId) {
    const zone = document.getElementById(zoneId);
    const input = document.getElementById(inputId);
    const label = document.getElementById(labelId);
    if (!zone || !input) return;

    zone.addEventListener("click", () => input.click());

    ["dragenter", "dragover"].forEach(name => {
        zone.addEventListener(name, (e) => {
            e.preventDefault();
            zone.classList.add("dragover");
        });
    });

    ["dragleave", "drop"].forEach(name => {
        zone.addEventListener(name, (e) => {
            e.preventDefault();
            zone.classList.remove("dragover");
        });
    });

    zone.addEventListener("drop", (e) => {
        if (e.dataTransfer.files.length) {
            input.files = e.dataTransfer.files;
            showFileName(input.files[0].name, label);
        }
    });

    input.addEventListener("change", () => {
        if (input.files.length) {
            showFileName(input.files[0].name, label);
        }
    });
}

function showFileName(name, labelEl) {
    if (labelEl) {
        labelEl.innerText = "📄 Selected: " + name;
        labelEl.style.display = "inline-block";
    }
}

// --- Live Stats ---
async function loadStats() {
    try {
        const res = await fetch("/api/stats");
        if (res.ok) {
            const data = await res.json();
            document.getElementById("statTotalJobs").innerText = data.total_jobs || 0;
            document.getElementById("statTotalResumes").innerText = data.total_resumes || 0;
            document.getElementById("statTotalMatches").innerText = data.total_matches || 0;
            document.getElementById("statAvgScore").innerText = (data.avg_score || 0) + "%";
        }
    } catch (e) {
        console.warn("Could not load stats:", e);
    }
}

// --- Jobs Dropdown & Catalog ---
async function loadJobsCatalog() {
    try {
        const res = await fetch("/api/jobs");
        if (res.ok) {
            const data = await res.json();
            const selectEl = document.getElementById("existingJobSelect");
            const catalogGrid = document.getElementById("jobsCatalogGrid");

            if (selectEl) {
                selectEl.innerHTML = '<option value="">-- Or choose an active opening --</option>';
                data.jobs.forEach(j => {
                    const opt = document.createElement("option");
                    opt.value = j.id;
                    opt.innerText = `${j.title} (${j.company || 'Direct'}) - #${j.id}`;
                    selectEl.appendChild(opt);
                });
            }

            if (catalogGrid) {
                if (data.jobs.length === 0) {
                    catalogGrid.innerHTML = "<p class='text-muted'>No jobs found. Add one above or reseed dataset.</p>";
                    return;
                }
                catalogGrid.innerHTML = data.jobs.map(j => `
                    <div class="match-card">
                        <div>
                            <div class="match-title">${escapeHtml(j.title)}</div>
                            <div class="match-subtitle">🏢 ${escapeHtml(j.company)} | 📍 ${escapeHtml(j.location || 'Remote')}</div>
                            <p style="font-size: 0.85rem; color: #475569; margin-top: 0.75rem; line-height: 1.4;">
                                ${escapeHtml(j.preview)}
                            </p>
                        </div>
                        <div style="margin-top: 1rem; display: flex; justify-content: space-between; align-items: center;">
                            <span style="font-size: 0.75rem; color: #94a3b8;">Job ID: #${j.id}</span>
                            <button class="btn btn-outline btn-sm" onclick="quickMatchJob(${j.id})">Find Candidates</button>
                        </div>
                    </div>
                `).join("");
            }
        }
    } catch (e) {
        console.warn("Could not load jobs catalog:", e);
    }
}

// --- Initialize Form Handlers ---
function initForms() {
    // 1. Candidate Match Resume Form
    const resumeForm = document.getElementById("matchResumeForm");
    if (resumeForm) {
        resumeForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            const btn = document.getElementById("btnMatchResume");
            const spinner = btn.querySelector(".spinner");
            const formData = new FormData(resumeForm);

            const fileInput = document.getElementById("resumeFileInput");
            const textInput = document.getElementById("resumeTextInput");

            if ((!fileInput.files || fileInput.files.length === 0) && !textInput.value.trim()) {
                showToast("Please upload a file or paste your resume text!");
                return;
            }

            btn.disabled = true;
            if (spinner) spinner.style.display = "inline-block";

            try {
                const res = await fetch("/api/match_resume", {
                    method: "POST",
                    body: formData
                });
                const data = await res.json();
                if (!res.ok) {
                    throw new Error(data.error || "Failed to analyze resume");
                }
                renderResumeMatchResults(data);
                loadStats();
                showToast("Resume analyzed & matched successfully!");
            } catch (err) {
                showToast("Error: " + err.message);
            } finally {
                btn.disabled = false;
                if (spinner) spinner.style.display = "none";
            }
        });
    }

    // 2. Recruiter Match Job Form
    const jobForm = document.getElementById("matchJobForm");
    if (jobForm) {
        jobForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            const btn = document.getElementById("btnMatchJob");
            const spinner = btn.querySelector(".spinner");
            const selectedJobId = document.getElementById("existingJobSelect").value;
            const fileInput = document.getElementById("jobFileInput");
            const textInput = document.getElementById("jobTextInput");

            btn.disabled = true;
            if (spinner) spinner.style.display = "inline-block";

            try {
                let res, data;
                if (selectedJobId) {
                    res = await fetch("/match", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ job_id: selectedJobId })
                    });
                    data = await res.json();
                    if (!res.ok) throw new Error(data.error || "Matching failed");
                    renderJobCandidateMatches({
                        job_title: data.job_title,
                        top_candidates: data.top_matches
                    });
                } else {
                    if ((!fileInput.files || fileInput.files.length === 0) && !textInput.value.trim()) {
                        throw new Error("Please upload a job description, paste text, or select an existing job!");
                    }
                    const formData = new FormData(jobForm);
                    res = await fetch("/api/match_job", {
                        method: "POST",
                        body: formData
                    });
                    data = await res.json();
                    if (!res.ok) throw new Error(data.error || "Matching failed");
                    renderJobCandidateMatches(data);
                }
                loadStats();
                loadJobsCatalog();
                showToast("Top candidates matched successfully!");
            } catch (err) {
                showToast("Error: " + err.message);
            } finally {
                btn.disabled = false;
                if (spinner) spinner.style.display = "none";
            }
        });
    }

    // 3. Add Job Form
    const addJobForm = document.getElementById("addNewJobForm");
    if (addJobForm) {
        addJobForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            const title = document.getElementById("newJobTitle").value;
            const company = document.getElementById("newJobCompany").value;
            const location = document.getElementById("newJobLocation").value;
            const description = document.getElementById("newJobDescription").value;

            try {
                const res = await fetch("/api/add_job", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ title, company, location, description })
                });
                const data = await res.json();
                if (!res.ok) throw new Error(data.error || "Failed to add job");
                addJobForm.reset();
                showToast(`Job '${data.title}' added successfully!`);
                loadStats();
                loadJobsCatalog();
            } catch (err) {
                showToast("Error: " + err.message);
            }
        });
    }
}

function quickMatchJob(jobId) {
    const tabRecruiter = document.querySelector('[data-tab="recruiter-tab"]');
    if (tabRecruiter) tabRecruiter.click();
    const selectEl = document.getElementById("existingJobSelect");
    if (selectEl) {
        selectEl.value = jobId;
        const form = document.getElementById("matchJobForm");
        if (form) form.dispatchEvent(new Event('submit'));
    }
}

// --- Render Resume Results ---
function renderResumeMatchResults(data) {
    const resultsContainer = document.getElementById("resumeResultsContainer");
    resultsContainer.style.display = "block";
    resultsContainer.scrollIntoView({ behavior: 'smooth' });

    const c = data.candidate;
    const profileHtml = `
        <div class="profile-card">
            <div class="profile-header">
                <div>
                    <h3 style="font-size: 1.3rem; font-weight: 700; color: #1e293b;">👤 ${escapeHtml(c.name || 'Candidate')}</h3>
                    <div class="profile-meta" style="margin-top: 0.35rem;">
                        ${c.email ? `<span>📧 ${escapeHtml(c.email)}</span>` : ''}
                        ${c.phone ? `<span>📞 ${escapeHtml(c.phone)}</span>` : ''}
                        ${c.experience_years ? `<span>💼 ${c.experience_years}+ Years Experience</span>` : ''}
                    </div>
                </div>
                <div class="badge-ai">Profile Parsed & Indexed</div>
            </div>

            ${c.education && c.education.length ? `
                <div style="font-size: 0.85rem; color: #475569; margin-bottom: 0.75rem;">
                    <strong>🎓 Education:</strong> ${c.education.map(e => escapeHtml(e)).join(", ")}
                </div>
            ` : ''}

            <div class="skill-section">
                <h5>Extracted Skills (${c.skills ? c.skills.length : 0})</h5>
                <div class="skill-pills">
                    ${c.skills && c.skills.length ? c.skills.map(s => `<span class="pill pill-general">${escapeHtml(s)}</span>`).join('') : '<span style="font-size:0.8rem; color:#94a3b8;">No skills automatically detected.</span>'}
                </div>
            </div>
        </div>
    `;

    document.getElementById("candidateProfileBox").innerHTML = profileHtml;

    const matchesHtml = data.top_matches.map(m => {
        const scoreClass = m.score >= 70 ? 'high' : (m.score >= 45 ? 'medium' : 'low');
        return `
            <div class="match-card">
                <div>
                    <div class="match-header">
                        <div>
                            <div class="match-title">${escapeHtml(m.job_title)}</div>
                            <div class="match-subtitle">🏢 ${escapeHtml(m.company)} | 📍 ${escapeHtml(m.location)}</div>
                        </div>
                        <div class="score-badge ${scoreClass}">${m.score}%</div>
                    </div>

                    <div class="score-bar-container">
                        <div class="score-bar">
                            <div class="score-fill ${scoreClass}" style="width: ${m.score}%;"></div>
                        </div>
                    </div>

                    <div style="display: flex; gap: 1rem; font-size: 0.75rem; color: #64748b; margin-bottom: 0.75rem;">
                        <span>🧠 Semantic: <strong>${m.sbert_score}%</strong></span>
                        <span>⚡ Skills Match: <strong>${m.skill_score}%</strong></span>
                    </div>

                    <p style="font-size: 0.85rem; color: #334155; line-height: 1.4; margin-bottom: 0.75rem;">
                        ${escapeHtml(m.preview)}
                    </p>

                    <div class="skill-section">
                        <h5>Matched Skills (${m.matched_skills.length})</h5>
                        <div class="skill-pills">
                            ${m.matched_skills.length ? m.matched_skills.map(s => `<span class="pill pill-matched">✓ ${escapeHtml(s)}</span>`).join('') : '<span style="font-size:0.75rem; color:#94a3b8;">None identified</span>'}
                        </div>
                    </div>

                    ${m.missing_skills && m.missing_skills.length ? `
                        <div class="skill-section" style="margin-top: 0.5rem;">
                            <h5 style="color: #b91c1c;">Skill Gap / To Learn (${m.missing_skills.length})</h5>
                            <div class="skill-pills">
                                ${m.missing_skills.map(s => `<span class="pill pill-missing">✕ ${escapeHtml(s)}</span>`).join('')}
                            </div>
                        </div>
                    ` : ''}

                    ${m.score >= 60 ? `
                        <div style="margin-top: 1rem; padding-top: 0.75rem; border-top: 1px solid #f1f5f9; display: flex; justify-content: space-between; align-items: center;">
                            <span style="font-size: 0.75rem; color: #16a34a; font-weight: 600;">✓ Qualified for Interview (≥60%)</span>
                            <a href="/interview?candidate=${encodeURIComponent(c.name || 'Candidate')}&role=${encodeURIComponent(m.job_title)}&company=${encodeURIComponent(m.company)}&score=${m.score}" class="btn btn-primary btn-sm" style="font-size:0.8rem; background: #1a73e8;">
                                Schedule Interview 📹
                            </a>
                        </div>
                    ` : `
                        <div style="margin-top: 0.75rem; padding-top: 0.5rem; border-top: 1px solid #f1f5f9; display: flex; justify-content: space-between; align-items: center;">
                            <span style="font-size: 0.75rem; color: #94a3b8; font-style: italic;">Below 60% threshold for interview</span>
                            <span style="background:#f1f5f9; color:#94a3b8; font-size:0.75rem; padding: 0.2rem 0.5rem; border-radius: 4px;">Not Shortlisted</span>
                        </div>
                    `}
                </div>
            </div>
        `;
    }).join("");

    document.getElementById("resumeMatchesGrid").innerHTML = matchesHtml;
}

// --- Render Recruiter Results ---
function renderJobCandidateMatches(data) {
    const container = document.getElementById("jobResultsContainer");
    container.style.display = "block";
    container.scrollIntoView({ behavior: 'smooth' });

    document.getElementById("matchedJobTitle").innerText = data.job_title || "Job Position";

    const candidates = data.top_candidates || [];
    if (!candidates.length) {
        document.getElementById("jobCandidatesGrid").innerHTML = "<p class='text-muted'>No matching candidates found.</p>";
        return;
    }

    const html = candidates.map(c => {
        const score = c.score || 0;
        const scoreClass = score >= 70 ? 'high' : (score >= 45 ? 'medium' : 'low');
        const matched = c.matched_skills || [];
        const missing = c.missing_skills || [];

        return `
            <div class="match-card">
                <div>
                    <div class="match-header">
                        <div>
                            <div class="match-title">${escapeHtml(c.candidate_name)}</div>
                            <div class="match-subtitle">📧 ${escapeHtml(c.email || 'Email not provided')}</div>
                        </div>
                        <div class="score-badge ${scoreClass}">${score}%</div>
                    </div>

                    <div class="score-bar-container">
                        <div class="score-bar">
                            <div class="score-fill ${scoreClass}" style="width: ${score}%;"></div>
                        </div>
                    </div>

                    <p style="font-size: 0.85rem; color: #475569; margin-bottom: 0.75rem; line-height: 1.4;">
                        ${escapeHtml(c.preview || '')}
                    </p>

                    <div class="skill-section">
                        <h5>Matched Qualifications (${matched.length})</h5>
                        <div class="skill-pills">
                            ${matched.length ? matched.map(s => `<span class="pill pill-matched">✓ ${escapeHtml(s)}</span>`).join('') : '<span style="font-size:0.75rem; color:#94a3b8;">None</span>'}
                        </div>
                    </div>

                    ${missing.length ? `
                        <div class="skill-section" style="margin-top: 0.5rem;">
                            <h5 style="color: #b91c1c;">Missing Requirements (${missing.length})</h5>
                            <div class="skill-pills">
                                ${missing.map(s => `<span class="pill pill-missing">✕ ${escapeHtml(s)}</span>`).join('')}
                            </div>
                        </div>
                    ` : ''}

                    ${score >= 60 ? `
                        <div style="margin-top: 1rem; padding-top: 0.75rem; border-top: 1px solid #f1f5f9; display: flex; justify-content: space-between; align-items: center;">
                            <span style="font-size: 0.75rem; color: #16a34a; font-weight: 600;">✓ Shortlisted (≥60%)</span>
                            <a href="/interview?candidate=${encodeURIComponent(c.candidate_name)}&role=${encodeURIComponent(data.job_title || 'Role')}&score=${score}" class="btn btn-primary btn-sm" style="font-size:0.8rem; background: #1a73e8;">
                                Invite to Interview 📹
                            </a>
                        </div>
                    ` : `
                        <div style="margin-top: 0.75rem; padding-top: 0.5rem; border-top: 1px solid #f1f5f9; display: flex; justify-content: space-between; align-items: center;">
                            <span style="font-size: 0.75rem; color: #94a3b8; font-style: italic;">Below 60% threshold for interview</span>
                            <span style="background:#f1f5f9; color:#94a3b8; font-size:0.75rem; padding: 0.2rem 0.5rem; border-radius: 4px;">Not Shortlisted</span>
                        </div>
                    `}
                </div>
            </div>
        `;
    }).join("");

    document.getElementById("jobCandidatesGrid").innerHTML = html;
}

// --- Utilities ---
function showToast(msg) {
    let toast = document.getElementById("toastNotification");
    if (!toast) {
        toast = document.createElement("div");
        toast.id = "toastNotification";
        toast.className = "toast";
        document.body.appendChild(toast);
    }
    toast.innerText = msg;
    toast.style.display = "block";
    setTimeout(() => {
        toast.style.display = "none";
    }, 3500);
}

function escapeHtml(text) {
    if (!text) return "";
    return String(text)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}
