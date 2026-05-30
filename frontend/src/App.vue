<template>
  <div class="dashboard-container">
    <header class="glass-panel">
      <h1>Reddit Swarm Intelligence</h1>
      <p>Node.js & FastAPI Collaborative Dashboard</p>
    </header>

    <main>
      <div class="swarm-chat glass-panel">
        <div class="chat-history">
          <div v-for="msg in messages" :key="msg.id" class="message">
            <strong>{{ msg.role }}:</strong> {{ msg.text }}
          </div>
        </div>
        
        <div class="input-area">
          <input 
            v-model="userQuery" 
            @keyup.enter="askSwarm" 
            placeholder="Ask the Text-to-SQL Swarm..." 
          />
          <button @click="askSwarm">Ask Swarm</button>
        </div>
      </div>
      
      <div class="agent-debug glass-panel" v-if="lastEval">
        <h2>Critic Evaluation Audit</h2>
        <div class="code-block">
          <code>{{ lastEval.sql }}</code>
        </div>
        <p class="critic-log" :class="{ approved: lastEval.critic.includes('APPROVE') }">
          {{ lastEval.critic }}
        </p>
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref } from 'vue';

const messages = ref([{ id: 1, role: "System", text: "Dashboard connected. Ask a question about the Reddit DB!" }]);
const userQuery = ref('');
const lastEval = ref(null);

const askSwarm = async () => {
    if (!userQuery.value.trim()) return;
    
    messages.value.push({
        id: Date.now(),
        role: "User",
        text: userQuery.value
    });
    
    let currentQ = userQuery.value;
    userQuery.value = '';
    
    // Set a loading prompt while waiting for APIs!
    messages.value.push({
        id: "loading_msg",
        role: "System (Swarm)",
        text: `Executing autonomous search logic evaluating ${currentQ}... (BrightData scraping takes ~15 seconds)`
    });
    lastEval.value = null;

    try {
        const response = await fetch('http://localhost:8000/api/ask', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({query: currentQ})
        });
        
        const data = await response.json();
        
        // Remove loading
        messages.value = messages.value.filter(m => m.id !== "loading_msg");
        
        messages.value.push({
            id: Date.now()+2,
            role: "Swarm Answer",
            text: data.response
        });
        
        lastEval.value = {
            sql: data.logs.join('\n'), // Re-purposed code block to emit Swarm interaction logs
            critic: "Execution Logs Completed!"
        };
        
    } catch (e) {
        messages.value = messages.value.filter(m => m.id !== "loading_msg");
        messages.value.push({ id: Date.now()+3, role: "System Error", text: "Error connecting to backend API: " + e.message });
        
        lastEval.value = {
            sql: "Fetch error encountered.",
            critic: `Check if Python FastAPI running on port 8000. Stack: ${e.message}`
        };
    }
}
</script>

<style scoped>
.dashboard-container {
    max-width: 1200px;
    margin: 0 auto;
    padding: 2rem;
    display: flex;
    flex-direction: column;
    gap: 2rem;
    min-height: 100vh;
}

header {
    padding: 2rem;
    text-align: center;
    background: linear-gradient(135deg, rgba(88, 101, 242, 0.2), rgba(255, 69, 58, 0.1));
}

header h1 {
    margin: 0;
    font-size: 2.5rem;
    background: -webkit-linear-gradient(#4facfe, #00f2fe);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}

main {
    display: grid;
    grid-template-columns: 2fr 1fr;
    gap: 2rem;
}

.swarm-chat {
    padding: 1.5rem;
    display: flex;
    flex-direction: column;
    height: 600px;
}

.chat-history {
    flex: 1;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 1rem;
    margin-bottom: 1rem;
}

.message {
    padding: 1rem;
    border-radius: 8px;
    background: rgba(255, 255, 255, 0.03);
}

.input-area {
    display: flex;
    gap: 1rem;
}

input {
    flex: 1;
    padding: 1rem;
    border-radius: 8px;
    border: 1px solid rgba(255,255,255,0.2);
    background: transparent;
    color: white;
    font-family: inherit;
    font-size: 1rem;
}

input:focus {
    outline: none;
    border-color: #4facfe;
}

button {
    padding: 0 2rem;
    border-radius: 8px;
    border: none;
    background: linear-gradient(135deg, #4facfe, #00f2fe);
    color: #111;
    font-weight: 700;
    cursor: pointer;
    transition: transform 0.2s;
}

button:hover {
    transform: scale(1.05);
}

.agent-debug {
    padding: 1.5rem;
}

.code-block {
    background: #161b22;
    padding: 1rem;
    border-radius: 6px;
    font-family: monospace;
    font-size: 0.9rem;
    color: #a5d6ff;
    overflow-x: auto;
}

.critic-log {
    margin-top: 1rem;
    padding: 1rem;
    border-left: 4px solid #ff453a;
    background: rgba(255, 69, 58, 0.1);
}

.critic-log.approved {
    border-left-color: #34c759;
    background: rgba(52, 199, 89, 0.1);
}
</style>
