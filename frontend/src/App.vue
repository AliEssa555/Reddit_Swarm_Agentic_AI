<template>
  <div class="dashboard-container">
    <aside class="sidebar glass-panel">
      <div class="logo">
        <div class="logo-icon"></div>
        <h2>Reddit Swarm</h2>
      </div>
      <nav>
        <button 
          :class="{ active: currentView === 'swarm' }" 
          @click="currentView = 'swarm'"
        >
          <span class="icon">💬</span> Swarm Chat
        </button>
        <button 
          :class="{ active: currentView === 'topics' }" 
          @click="currentView = 'topics'"
        >
          <span class="icon">📊</span> Topic Hierarchy
        </button>
        <button 
          :class="{ active: currentView === 'history' }" 
          @click="currentView = 'history'"
        >
          <span class="icon">👁️</span> Agent Observability
        </button>
      </nav>
      <div class="system-status">
        <div class="status-indicator online"></div>
        <span>FastAPI & LLM Online</span>
      </div>
    </aside>

    <main class="content-area">
      <!-- Swarm Chat View -->
      <section v-if="currentView === 'swarm'" class="view-section swarm-view">
        <div class="swarm-chat glass-panel">
          <div class="chat-header">
            <h3>Live Intelligence Swarm</h3>
            <span class="subtitle">Scraping Reddit via Bright Data & Qwen2.5</span>
          </div>
          <div class="chat-history" ref="chatScroll">
            <div 
              v-for="msg in messages" 
              :key="msg.id" 
              class="message-wrapper"
              :class="msg.role.toLowerCase()"
            >
              <div class="message-content">
                <span class="role-badge">{{ msg.role }}</span>
                <p>{{ msg.text }}</p>
              </div>
            </div>
          </div>
          
          <div class="input-area">
            <input 
              v-model="userQuery" 
              @keyup.enter="askSwarm" 
              placeholder="Ask for real-time Reddit analysis..." 
              :disabled="isLoading"
            />
            <button @click="askSwarm" :disabled="isLoading">
              <span v-if="!isLoading">Send Query</span>
              <span v-else class="loader"></span>
            </button>
          </div>
        </div>
        
        <div class="agent-audit glass-panel" v-if="lastEval">
          <h3>Swarm Execution Audit</h3>
          <div class="audit-logs">
            <div v-for="(log, index) in lastEval.logs" :key="index" class="log-line">
              {{ log }}
            </div>
          </div>
        </div>
      </section>

      <!-- Topic Hierarchy View -->
      <section v-if="currentView === 'topics'" class="view-section topics-view">
        <div class="view-header">
          <div class="header-main">
            <h2>Topic Analytics & Scraping</h2>
            <p>Explore autonomous taxonomy or trigger targeted Swarm Scraping</p>
          </div>
          <button v-if="!selectedCategory" class="action-btn create-btn" @click="showCreateModal = true">+ Create Category</button>
        </div>
        
        <div v-if="selectedCategory" class="category-detail glass-panel">
          <div class="detail-header">
            <h3>{{ selectedCategory.name }} <span class="badge">Deep Dive</span></h3>
            <div class="detail-actions">
              <button class="delete-btn-link" @click="confirmDelete(selectedCategory)">Delete Category</button>
              <button class="back-btn" @click="selectedCategory = null">← Back to Overview</button>
            </div>
          </div>
          
          <div class="tabs">
            <button :class="{active: activeTab === 'analysis'}" @click="activeTab = 'analysis'">Historical Analysis</button>
            <button :class="{active: activeTab === 'charts'}" @click="activeTab = 'charts'">Data Visualizations</button>
            <button :class="{active: activeTab === 'scrape'}" @click="activeTab = 'scrape'">Batch Scrape</button>
          </div>
          
          <div v-if="activeTab === 'analysis'" class="tab-content">
             <div v-if="!categoryAnalysis && !isAnalyzing" class="analysis-init">
                <p>Ready to deeply analyze historical perspectives within <strong>{{ selectedCategory.name }}</strong>.</p>
                <button class="action-btn" @click="generateAnalysis">Synthesize Historical Insights</button>
             </div>
             <div v-else-if="isAnalyzing" class="loading-state">
                <div class="loader"></div>
                <p>Synthesizing insights using Qwen2.5...</p>
             </div>
             <div v-else class="analysis-box">
                <div v-html="formattedAnalysis" class="markdown-body"></div>
             </div>
          </div>
          
          <div v-show="activeTab === 'charts'" class="tab-content">
            <p>Subtopic Post Distribution within <strong>{{ selectedCategory.name }}</strong></p>
            <div class="chart-container" style="position: relative; height:400px; width:100%; margin-top: 1.5rem; background: rgba(0,0,0,0.2) padding: 1rem; border-radius: 8px;">
              <canvas ref="chartCanvas"></canvas>
            </div>
            <div class="chart-filters" style="margin-top: 1rem; display: flex; justify-content: flex-end;">
               <button class="action-btn small" @click="loadCharts">Refresh Data</button>
            </div>
          </div>
          
          <div v-if="activeTab === 'scrape'" class="tab-content">
            <p>Targeted Data Extraction for <strong>{{ selectedCategory.name }}</strong></p>
            <div class="scrape-form">
              <div class="form-group">
                <label>Number of Posts</label>
                <input type="number" v-model="scrapeForm.num_posts" min="10" max="1000" />
              </div>
              <div class="form-group">
                <label>Comments Per Post</label>
                <input type="number" v-model="scrapeForm.num_comments" min="0" max="100" />
              </div>
              <div class="form-group">
                <label>Time Filter</label>
                <select v-model="scrapeForm.time_filter">
                  <option value="Past 24 hours">Past 24 hours</option>
                  <option value="Past week">Past week</option>
                  <option value="Past month">Past month</option>
                  <option value="Past year">Past year</option>
                  <option value="All time">All time</option>
                </select>
              </div>
              <button class="action-btn" @click="submitScrape" :disabled="isScraping">
                <span v-if="!isScraping">Initialize Swarm Scraper</span>
                <span v-else class="loader"></span>
              </button>
            </div>

            <div v-if="isScraping" class="scrape-status loading">
              <div class="loader"></div>
              <p>Scraper is running in the background. Collecting <strong>{{ scrapeForm.num_posts }}</strong> posts with <strong>{{ scrapeForm.num_comments }}</strong> comments each from BrightData...</p>
            </div>

            <div v-if="scrapeResult" :class="['scrape-status', scrapeResult.success ? 'result-success' : 'result-error']">
              <span class="result-icon">{{ scrapeResult.success ? '✅' : '❌' }}</span>
              <div>
                <strong>{{ scrapeResult.success ? 'Scrape Complete' : 'Scrape Failed' }}</strong>
                <p>{{ scrapeResult.message }}</p>
              </div>
            </div>
          </div>
        </div>

        <div v-else class="topic-grid">
          <div 
            v-for="cat in categories" 
            :key="cat.id" 
            class="category-card glass-panel"
            @click="selectCategory(cat)"
          >
            <div class="category-header">
              <h4>{{ cat.name }}</h4>
            </div>
            <ul class="topic-list">
              <li v-for="top in cat.topics.slice(0, 5)" :key="top.id" class="topic-item">
                <span class="dot"></span> {{ top.name }}
              </li>
              <li v-if="cat.topics.length > 5" class="more">+{{ cat.topics.length - 5 }} more topics</li>
            </ul>
          </div>
        </div>

        <!-- Create Category Modal -->
        <div v-if="showCreateModal" class="modal-overlay" @click.self="showCreateModal = false">
          <div class="modal-content glass-panel">
            <div class="modal-header">
              <h3>Create New Category</h3>
              <button class="close-btn" @click="showCreateModal = false">×</button>
            </div>
            <div class="modal-body">
              <div class="form-group">
                <label>Category Name</label>
                <input v-model="newCategory.name" placeholder="e.g. Cybersecurity, Space Tech..." />
              </div>
              <div class="form-group" style="margin-top: 1rem;">
                <label>Description (Optional)</label>
                <textarea v-model="newCategory.description" placeholder="What is this category about?"></textarea>
              </div>
              <div v-if="createError" class="error-text">{{ createError }}</div>
            </div>
            <div class="modal-footer">
              <button class="nav-item" @click="showCreateModal = false">Cancel</button>
              <button class="action-btn" :disabled="!newCategory.name" @click="createCategory">
                <span v-if="isCreating">Creating...</span>
                <span v-else>Create Category</span>
              </button>
            </div>
          </div>
        </div>
      </section>

      <!-- Agent Observability View -->
      <section v-if="currentView === 'history'" class="view-section history-view">
        <div class="view-header">
          <h2>Agent Observability</h2>
          <p>Trace analysis and generated SQL</p>
        </div>
        <div class="history-list">
          <div v-for="run in history" :key="run.id" class="run-card glass-panel">
            <div class="run-header">
              <span class="run-time">{{ formatTime(run.created_at) }}</span>
              <span class="run-agent">{{ run.agent_name }}</span>
            </div>
            <div class="run-query">
              <strong>Query:</strong> {{ run.task }}
            </div>
            <div class="run-details">
              <details>
                <summary>View Full Execution Trace</summary>
                <div class="audit-logs small">
                  {{ run.evaluation }}
                </div>
              </details>
            </div>
          </div>
        </div>
      </section>
    </main>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick, watch, computed } from 'vue';
import { marked } from 'marked';
import { Chart, registerables } from 'chart.js';
Chart.register(...registerables);

const currentView = ref('swarm');
const messages = ref([{ id: 1, role: "System", text: "Swarm initialized. Ready for real-time Reddit analysis." }]);
const userQuery = ref('');
const lastEval = ref(null);
const isLoading = ref(false);
const categories = ref([]);
const history = ref([]);
const chatScroll = ref(null);

// Drill Down State
const selectedCategory = ref(null);
const activeTab = ref('analysis');
const isAnalyzing = ref(false);
const categoryAnalysis = ref('');
const scrapeForm = ref({ num_posts: 100, num_comments: 10, time_filter: 'Past month' });
const scrapeResult = ref(null);

// Create Category Modal State
const showCreateModal = ref(false);
const isCreating = ref(false);
const createError = ref('');
const newCategory = ref({ name: '', description: '' });

const createCategory = async () => {
    if (!newCategory.value.name) return;
    isCreating.value = true;
    createError.value = '';
    try {
        const res = await fetch(`http://localhost:8000/api/category`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(newCategory.value)
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Failed to create category');
        
        // Success
        await fetchData(); // Refresh list
        showCreateModal.value = false;
        newCategory.value = { name: '', description: '' };
    } catch (e) {
        createError.value = e.message;
    } finally {
        isCreating.value = false;
    }
};

const formattedAnalysis = computed(() => {
    return categoryAnalysis.value ? marked(categoryAnalysis.value) : '';
});

const chartCanvas = ref(null);
let chartInstance = null;

const loadCharts = async () => {
    if (!selectedCategory.value) return;
    try {
        const res = await fetch(`http://localhost:8000/api/category/${selectedCategory.value.id}/metrics`);
        const data = await res.json();
        
        if (data.error) throw new Error(data.error);

        nextTick(() => {
            if (chartInstance) {
                chartInstance.destroy();
            }
            if (chartCanvas.value) {
                chartInstance = new Chart(chartCanvas.value, {
                    type: 'bar',
                    data: data,
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: { labels: { color: '#a5d6ff' } }
                        },
                        scales: {
                            y: { ticks: { color: '#8b949e', stepSize: 1 }, grid: { color: 'rgba(255,255,255,0.05)' } },
                            x: { ticks: { color: '#8b949e' }, grid: { color: 'rgba(255,255,255,0.05)' } }
                        }
                    }
                });
            }
        });
    } catch (e) {
        console.error("Chart load failed:", e);
    }
};

watch(activeTab, (newTab) => {
    if (newTab === 'charts') {
        loadCharts();
    }
});

const formatTime = (iso) => {
    return new Date(iso).toLocaleTimeString();
};


const scrollToBottom = () => {
    nextTick(() => {
        if (chatScroll.value) {
            chatScroll.value.scrollTop = chatScroll.value.scrollHeight;
        }
    });
};

const fetchData = async () => {
    try {
        const [topicsRes, historyRes] = await Promise.all([
            fetch('http://localhost:8000/api/topics'),
            fetch('http://localhost:8000/api/history')
        ]);
        categories.value = await topicsRes.json();
        history.value = await historyRes.json();
    } catch (e) {
        console.error("Failed to fetch dashboard data:", e);
    }
};

onMounted(() => {
    fetchData();
});

watch(currentView, (newView) => {
    if (newView !== 'swarm') fetchData();
    if (newView !== 'topics') selectedCategory.value = null; // Reset selection on navigate away
});

const selectCategory = async (cat) => {
    selectedCategory.value = cat;
    activeTab.value = 'analysis';
    categoryAnalysis.value = '';
    isAnalyzing.value = false;
    scrapeMessage.value = '';
};

const generateAnalysis = async () => {
    if (!selectedCategory.value) return;
    isAnalyzing.value = true;
    categoryAnalysis.value = '';
    try {
        const res = await fetch(`http://localhost:8000/api/category/${selectedCategory.value.id}/analysis`);
        const data = await res.json();
        categoryAnalysis.value = data.response || data.error;
    } catch (e) {
        categoryAnalysis.value = "Failed to communicate with LLM.";
    } finally {
        isAnalyzing.value = false;
    }
};

const submitScrape = async () => {
    isScraping.value = true;
    scrapeResult.value = null;
    
    const payload = {
        category_id: selectedCategory.value.id,
        num_posts: scrapeForm.value.num_posts,
        num_comments: scrapeForm.value.num_comments,
        time_filter: scrapeForm.value.time_filter
    };
    
    try {
        const res = await fetch('http://localhost:8000/api/category/scrape', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (res.ok) {
            scrapeResult.value = { success: true, message: data.message || 'Scraping job completed successfully.' };
        } else {
            scrapeResult.value = { success: false, message: data.detail || data.error || 'Server returned an error.' };
        }
    } catch (e) {
        scrapeResult.value = { success: false, message: 'Failed to connect to scraper backend. Is the server running?' };
    } finally {
        isScraping.value = false;
    }
};

const askSwarm = async () => {
    if (!userQuery.value.trim() || isLoading.value) return;
    
    isLoading.value = true;
    const currentQ = userQuery.value;
    userQuery.value = '';
    
    messages.value.push({
        id: Date.now(),
        role: "User",
        text: currentQ
    });
    
    scrollToBottom();

    try {
        const response = await fetch('http://localhost:8000/api/ask', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({query: currentQ})
        });
        
        const data = await response.json();
        
        messages.value.push({
            id: Date.now()+1,
            role: "Swarm",
            text: data.response
        });
        
        lastEval.value = {
            logs: data.logs
        };
        
        scrollToBottom();
        fetchData(); // Update history and topics
    } catch (e) {
        messages.value.push({ id: Date.now()+2, role: "Error", text: "Connection failure: " + e.message });
    } finally {
        isLoading.value = false;
    }
};

const confirmDelete = async (cat) => {
    if (confirm(`Are you sure you want to delete '${cat.name}'? This will remove all associated scrapes and analysis results forever.`)) {
        try {
            const res = await fetch(`http://localhost:8000/api/category/${cat.id}`, {
                method: 'DELETE'
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || 'Delete failed');
            
            selectedCategory.value = null;
            await fetchData();
        } catch (e) {
            alert("Error deleting category: " + e.message);
        }
    }
};
</script>

<style scoped>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Outfit:wght@600;700&display=swap');

.dashboard-container {
    display: grid;
    grid-template-columns: 280px 1fr;
    height: 100vh;
    background: radial-gradient(circle at top right, #1a2236, #0d1117);
    color: #e6edf3;
    font-family: 'Inter', sans-serif;
    overflow: hidden;
}

/* Sidebar */
.sidebar {
    border-right: 1px solid rgba(255,255,255,0.05);
    display: flex;
    flex-direction: column;
    padding: 2rem 1.5rem;
    z-index: 10;
}

.logo {
    display: flex;
    align-items: center;
    gap: 1rem;
    margin-bottom: 3rem;
}

.logo-icon {
    width: 32px;
    height: 32px;
    background: linear-gradient(135deg, #4facfe, #00f2fe);
    border-radius: 8px;
}

.logo h2 {
    font-family: 'Outfit', sans-serif;
    font-size: 1.5rem;
    margin: 0;
    background: linear-gradient(to right, #fff, #a5d6ff);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}

nav {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    flex: 1;
}

nav button {
    display: flex;
    align-items: center;
    gap: 1rem;
    padding: 0.8rem 1rem;
    border-radius: 10px;
    border: none;
    background: transparent;
    color: #8b949e;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s;
    text-align: left;
}

nav button:hover {
    background: rgba(255,255,255,0.05);
    color: #fff;
}

nav button.active {
    background: rgba(79, 172, 254, 0.1);
    color: #4facfe;
    border-left: 3px solid #4facfe;
}

.system-status {
    display: flex;
    align-items: center;
    gap: 0.8rem;
    font-size: 0.8rem;
    color: #8b949e;
    padding-top: 1rem;
    border-top: 1px solid rgba(255,255,255,0.05);
}

.status-indicator {
    width: 8px;
    height: 8px;
    border-radius: 50%;
}

.status-indicator.online {
    background: #34c759;
    box-shadow: 0 0 10px rgba(52, 199, 89, 0.5);
}

/* Content Area */
.content-area {
    padding: 2rem;
    overflow-y: auto;
    background: rgba(0,0,0,0.2);
}

.view-section {
    max-width: 1000px;
    margin: 0 auto;
    animation: fadeIn 0.4s ease-out;
}

@keyframes fadeIn {
    from { opacity: 0; transform: translateY(10px); }
    to { opacity: 1; transform: translateY(0); }
}

.view-header {
    margin-bottom: 2rem;
}

.view-header h2 {
    font-family: 'Outfit', sans-serif;
    font-size: 2rem;
    margin: 0 0 0.5rem 0;
}

.view-header p {
    color: #8b949e;
}

/* Swarm Chat */
.swarm-view {
    display: grid;
    grid-template-columns: 1fr 340px;
    gap: 2rem;
    height: calc(100vh - 4rem);
}

.swarm-chat {
    display: flex;
    flex-direction: column;
    height: 100%;
}

.chat-header {
    padding: 1rem 1.5rem;
    border-bottom: 1px solid rgba(255,255,255,0.05);
}

.chat-header h3 { margin: 0; }
.chat-header .subtitle { font-size: 0.8rem; color: #8b949e; }

.chat-history {
    flex: 1;
    overflow-y: auto;
    padding: 1.5rem;
    display: flex;
    flex-direction: column;
    gap: 1.5rem;
}

.message-wrapper {
    display: flex;
    flex-direction: column;
}

.message-wrapper.user { align-items: flex-end; }
.message-wrapper.swarm { align-items: flex-start; }

.message-content {
    max-width: 85%;
    padding: 1rem;
    border-radius: 12px;
    background: rgba(255,255,255,0.03);
}

.user .message-content {
    background: rgba(79, 172, 254, 0.1);
    border: 1px solid rgba(79, 172, 254, 0.2);
}

.role-badge {
    font-size: 0.7rem;
    font-weight: 700;
    text-transform: uppercase;
    color: #8b949e;
    margin-bottom: 0.5rem;
    display: block;
}

.message-content p { margin: 0; line-height: 1.5; }

.input-area {
    padding: 1.5rem;
    background: rgba(0,0,0,0.2);
    display: flex;
    gap: 1rem;
}

.input-area input {
    flex: 1;
    background: rgba(255,255,255,0.05);
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 8px;
    padding: 0.8rem 1rem;
    color: white;
    font-family: inherit;
}

.input-area input:focus {
    outline: none;
    border-color: #4facfe;
}

.input-area button {
    background: linear-gradient(135deg, #4facfe, #00f2fe);
    border: none;
    border-radius: 8px;
    padding: 0 1.5rem;
    color: #0d1117;
    font-weight: 600;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    min-width: 120px;
}

.action-btn.small {
    padding: 0.5rem 1rem;
    font-size: 0.9rem;
    min-width: auto;
}

/* Audit Logs */
.audit-logs {
    background: #010409;
    padding: 1rem;
    border-radius: 8px;
    font-family: monospace;
    font-size: 0.8rem;
    color: #7ee787;
    overflow-y: auto;
    height: 500px;
}

.log-line {
    border-bottom: 1px solid rgba(255,255,255,0.03);
    padding: 0.3rem 0;
}

/* Topic Grid & Detail */
.topic-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
    gap: 1.5rem;
}

.category-card {
    padding: 1.5rem;
    cursor: pointer;
    transition: transform 0.2s, box-shadow 0.2s;
    border: 1px solid rgba(255,255,255,0.05);
}

.category-card:hover {
    transform: translateY(-5px);
    border-color: #4facfe;
    box-shadow: 0 10px 30px rgba(79, 172, 254, 0.1);
}

.category-card h4 {
    margin: 0 0 1rem 0;
    color: #4facfe;
    font-size: 1.2rem;
}

.topic-list {
    list-style: none;
    padding: 0;
    margin: 0;
    display: flex;
    flex-wrap: wrap;
    gap: 0.8rem;
}

.topic-list li {
    background: rgba(255,255,255,0.05);
    padding: 0.4rem 0.8rem;
    border-radius: 6px;
    font-size: 0.9rem;
    display: flex;
    align-items: center;
    gap: 0.5rem;
}

.dot { width: 6px; height: 6px; background: #00f2fe; border-radius: 50%; }

.category-detail {
    padding: 2rem;
    animation: fadeIn 0.3s ease-out;
}

.detail-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1.5rem;
}

.detail-header h3 {
    margin: 0;
    font-size: 1.8rem;
    display: flex;
    align-items: center;
    gap: 1rem;
}

.badge {
    font-size: 0.8rem;
    background: rgba(79, 172, 254, 0.2);
    color: #a5d6ff;
    padding: 0.3rem 0.6rem;
    border-radius: 4px;
    font-weight: 500;
}

.back-btn {
    background: transparent;
    border: 1px solid rgba(255,255,255,0.2);
    color: #fff;
    padding: 0.5rem 1rem;
    border-radius: 6px;
    cursor: pointer;
    transition: all 0.2s;
}

.back-btn:hover {
    background: rgba(255,255,255,0.1);
}

.delete-btn-link {
    background: transparent;
    border: none;
    color: #ff453a;
    font-size: 0.9rem;
    margin-right: 1.5rem;
    cursor: pointer;
    opacity: 0.7;
    transition: opacity 0.2s;
}

.delete-btn-link:hover {
    opacity: 1;
    text-decoration: underline;
}

.detail-actions {
    display: flex;
    align-items: center;
}

.tabs {
    display: flex;
    gap: 1rem;
    border-bottom: 1px solid rgba(255,255,255,0.1);
    margin-bottom: 2rem;
}

.tabs button {
    background: none;
    border: none;
    padding: 1rem 1.5rem;
    color: #8b949e;
    cursor: pointer;
    font-weight: 600;
    font-size: 1rem;
    border-bottom: 2px solid transparent;
}

.tabs button.active {
    color: #4facfe;
    border-bottom-color: #4facfe;
}

.analysis-box {
    background: rgba(0,0,0,0.2);
    padding: 2rem;
    border-radius: 8px;
    border-left: 4px solid #00f2fe;
}

.analysis-init {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 1.5rem;
    padding: 3rem 1rem;
    background: rgba(0,0,0,0.2);
    border-radius: 8px;
    text-align: center;
}

.analysis-init p {
    color: #e6edf3;
    font-size: 1.1rem;
}

.analysis-init .action-btn {
    min-width: 250px;
}

.markdown-body {
    line-height: 1.6;
    color: #e6edf3;
    font-size: 0.95rem;
}

.markdown-body :deep(h1), 
.markdown-body :deep(h2), 
.markdown-body :deep(h3), 
.markdown-body :deep(h4) {
    margin-top: 1.5rem;
    margin-bottom: 0.8rem;
    color: #fff;
}

.markdown-body :deep(ul) {
    padding-left: 1.5rem;
    margin-bottom: 1rem;
}

.markdown-body :deep(li) {
    margin-bottom: 0.4rem;
}

.markdown-body :deep(strong) {
    color: #a5d6ff;
}

.scrape-form {
    display: grid;
    grid-template-columns: 1fr 1fr 1fr;
    gap: 1.5rem;
    background: rgba(0,0,0,0.2);
    padding: 2rem;
    border-radius: 8px;
    margin-top: 1rem;
}

.form-group {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
}

.form-group label {
    font-size: 0.9rem;
    color: #a5d6ff;
    font-weight: 600;
}

.form-group input, .form-group select {
    padding: 0.8rem;
    border-radius: 6px;
    background: #161b22;
    border: 1px solid rgba(255,255,255,0.1);
    color: #e6edf3;
    appearance: auto;
}

.form-group select option {
    background: #161b22;
    color: #e6edf3;
    padding: 0.5rem;
}

.action-btn {
    grid-column: 1 / -1;
    padding: 1rem;
    background: linear-gradient(135deg, #4facfe, #00f2fe);
    border: none;
    border-radius: 8px;
    color: #111;
    font-weight: bold;
    font-size: 1rem;
    cursor: pointer;
    display: flex;
    justify-content: center;
    transition: transform 0.2s;
}

.action-btn:hover {
    transform: translateY(-2px);
}

.toast-message {
    margin-top: 1rem;
    padding: 1rem;
    border-radius: 8px;
    text-align: center;
    font-weight: 500;
}

.toast-message.success {
    background: rgba(52, 199, 89, 0.1);
    color: #34c759;
    border: 1px solid rgba(52, 199, 89, 0.3);
}

.scrape-status {
    display: flex;
    align-items: center;
    gap: 1rem;
    padding: 1.2rem 1.5rem;
    border-radius: 8px;
    margin-top: 1.5rem;
    animation: fadeIn 0.3s ease;
}

.scrape-status.loading {
    background: rgba(79, 172, 254, 0.08);
    border: 1px solid rgba(79, 172, 254, 0.2);
    color: #a5d6ff;
}

.scrape-status.result-success {
    background: rgba(52, 199, 89, 0.1);
    border: 1px solid rgba(52, 199, 89, 0.3);
    color: #34c759;
}

.scrape-status.result-error {
    background: rgba(255, 69, 58, 0.1);
    border: 1px solid rgba(255, 69, 58, 0.3);
    color: #ff453a;
}

.scrape-status .result-icon {
    font-size: 1.5rem;
}

.scrape-status p {
    margin: 0.3rem 0 0;
    font-size: 0.9rem;
    opacity: 0.85;
}

@keyframes fadeIn {
    from { opacity: 0; transform: translateY(6px); }
    to { opacity: 1; transform: translateY(0); }
}

.loading-state {
    display: flex;
    align-items: center;
    gap: 1rem;
    color: #4facfe;
}

/* History View */
.history-list {
    display: flex;
    flex-direction: column;
    gap: 1rem;
}

.run-card {
    padding: 1.2rem;
}

.run-header {
    display: flex;
    justify-content: space-between;
    font-size: 0.8rem;
    color: #8b949e;
    margin-bottom: 0.8rem;
}

.run-query {
    margin-bottom: 1rem;
    font-size: 1.1rem;
}

details {
    padding: 0.8rem;
    background: rgba(0,0,0,0.2);
    border-radius: 8px;
}

summary { cursor: pointer; color: #4facfe; font-size: 0.9rem; }

.small { font-size: 0.7rem; height: auto; max-height: 200px; margin-top: 0.8rem; white-space: pre-wrap;}

.loader {
    width: 20px;
    height: 20px;
    border: 2px solid #fff;
    border-bottom-color: transparent;
    border-radius: 50%;
    animation: rotation 1s linear infinite;
}

.action-btn .loader {
    border-color: #111;
    border-bottom-color: transparent;
}

@keyframes rotation {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
}

/* Modal Styles */
.modal-overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0,0,0,0.8);
    backdrop-filter: blur(8px);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
    animation: fadeIn 0.2s ease-out;
}

.modal-content {
    width: 100%;
    max-width: 500px;
    padding: 2rem;
    border: 1px solid rgba(255,255,255,0.1);
}

.modal-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 2rem;
}

.modal-header h3 { margin: 0; font-size: 1.4rem; }

.close-btn {
    background: none;
    border: none;
    color: #8b949e;
    font-size: 2rem;
    cursor: pointer;
}

.modal-body {
    margin-bottom: 2rem;
}

.modal-body textarea {
    width: 100%;
    height: 100px;
    padding: 0.8rem;
    background: #161b22;
    border: 1px solid rgba(255,255,255,0.1);
    color: #e6edf3;
    border-radius: 6px;
    resize: none;
}

.modal-footer {
    display: flex;
    justify-content: flex-end;
    gap: 1rem;
}

.modal-footer .action-btn {
    grid-column: auto;
    min-width: 150px;
}

.error-text {
    color: #ff453a;
    font-size: 0.85rem;
    margin-top: 0.8rem;
}

.view-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 2.5rem;
}

.create-btn {
    grid-column: auto;
    padding: 0.6rem 1.2rem;
    font-size: 0.9rem;
}
</style>
