upage-py/
├── src/
│   ├── __init__.py
│   ├── server.py          # FastAPI + gRPC server
│   ├── crew_manager.py    # CrewAI agent orchestration
│   ├── neuro_engine.py    # Neuro-simulator streaming logic
│   ├── tts_engine.py      # Text-to-Speech service
│   ├── stt_engine.py      # Speech-to-Text service
│   ├── llm_service.py     # LLM integration
│   └── models/
│       ├── __init__.py
│       ├── chat.py
│       └── emotion.py
├── tests/
│   ├── test_chat.py
│   └── test_stream.py
├── requirements.txt
└── config.yaml
