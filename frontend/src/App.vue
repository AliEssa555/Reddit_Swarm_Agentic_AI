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
          <h2>Topic Hierarchy</h2>
          <p>Autonomous taxonomy generated from Reddit posts</p>
        </div>
        <div class="topic-grid" v-if="categories.length">
          <div v-for="cat in categories" :key="cat.id" class="category-card glass-panel">
            <div class="category-header">
              <h4>{{ cat.name }}</h4>
            </div>
            <ul class="topic-list">
              <li v-for="top in cat.topics" :key="top.id">
                <span class="dot"></span> {{ top.name }}
              </li>
            </ul>
          </div>
        </div>
        <div v-else class="empty-state glass-panel">
          <p>No topics extracted yet. Run a swarm query to populate the hierarchy.</p>
        </div>
      </section>

      <!-- Agent Observability View -->
      <section v-if="currentView === 'history'" class="view-section history-view">
        <div class="view-header">
          <h2>Agent Observability</h2>
          <p>Trace analysis, generated SQL, and execution latencies</p>
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
import { ref, onMounted, nextTick, watch } from 'vue';

const currentView = ref('swarm');
const messages = ref([{ id: 1, role: "System", text: "Swarm initialized. Ready for real-time Reddit analysis." }]);
const userQuery = ref('');
const lastEval = ref(null);
const isLoading = ref(false);
const categories = ref([]);
const history = ref([]);
const chatScroll = ref(null);

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
});

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

/* Topic Grid */
.topic-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
    gap: 1.5rem;
}

.category-card {
    padding: 1.5rem;
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
    border: 2px solid #0d1117;
    border-bottom-color: transparent;
    border-radius: 50%;
    animation: rotation 1s linear infinite;
}

@keyframes rotation {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
}
</style>
