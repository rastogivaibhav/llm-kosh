export const PROMPTS = [
  {
    id: 'boot-from-cartridge',
    title: 'Boot from Cartridge',
    description: 'Instruct the LLM to read the uploaded context pack and adopt the persona/rules defined in the cartridge.',
    tags: ['boot', 'initialize', 'setup', 'persona'],
    content: `Please read the attached AI Memory Cartridge context pack. 
Familiarize yourself with the system instructions, active goals, and the codebase context provided within.
Do not begin solving the problem immediately. First, confirm you have successfully initialized the cartridge and wait for my next instruction.`
  },
  {
    id: 'ask-for-receipt',
    title: 'Ask for MEMORY_RECEIPT',
    description: 'Ask the LLM to summarize its recent insights, decisions, and uncompleted work into a memory receipt.',
    tags: ['receipt', 'save', 'memory', 'context'],
    content: `We are going to pause our work for now. 
Please generate a MEMORY_RECEIPT.md containing a summary of what we've accomplished, any key decisions made, and the open next steps.
Format it clearly so that you can easily pick up where we left off when I upload this receipt in a future session.`
  },
  {
    id: 'generate-receipt-from-chat',
    title: 'Generate Receipt from Chat',
    description: 'Instruct the LLM to extract knowledge from the current chat history into a receipt for long-term storage.',
    tags: ['extract', 'knowledge', 'receipt', 'history'],
    content: `Review our entire conversation history above.
Extract any new technical knowledge, refactored code patterns, or bug fixes we discovered.
Provide these findings in a code block titled MEMORY_RECEIPT.md so I can save it to my local cartridge.`
  },
  {
    id: 'chatgpt-upload',
    title: 'ChatGPT Upload Instruction',
    description: 'Best practice for uploading context to ChatGPT.',
    tags: ['chatgpt', 'upload', 'openai', 'instructions'],
    content: `I am uploading a .zip file containing context for this project.
ChatGPT, please use your Advanced Data Analysis (Code Interpreter) to unzip and read the contents of this pack before answering my next prompt.`
  },
  {
    id: 'claude-upload',
    title: 'Claude Upload Instruction',
    description: 'Best practice for uploading context to Claude.',
    tags: ['claude', 'upload', 'anthropic', 'instructions'],
    content: `I am uploading a plain text bundle of my project context.
Claude, please review the enclosed files and system instructions to understand the architecture before we proceed.`
  },
  {
    id: 'gemini-upload',
    title: 'Gemini Upload Instruction',
    description: 'Best practice for uploading context to Gemini.',
    tags: ['gemini', 'upload', 'google', 'instructions'],
    content: `I have attached a project context pack.
Gemini, please parse the uploaded documents to align with my project's current state and goals.`
  }
];


