import express from 'express';
import cors from 'cors';

// Small Local Node.js API acting as an intermediary if you want
// to decouple the Python FastAPI logic from the FrontEnd!
const app = express();
const PORT = 3001;

app.use(cors());
app.use(express.json());

// Forwarding Requests to Python Swarm
app.post('/api/ask-swarm', async (req, res) => {
    // In the future this will hit your FastAPI Python endpoints
    res.json({
        message: "Swarm Response will stream here!",
        sql_used: "SELECT * FROM posts;",
        critic: "APPROVE",
        status: "Node.js proxy successful"
    });
});

app.listen(PORT, () => {
    console.log(`Node.js/Express Dashboard Backend running on http://localhost:${PORT}`);
});
