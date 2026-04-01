# Project_02 Pipeline Test Run Findings

An end-to-end test of the LangGraph pipeline was executed using a realistic Statement of Work (SOW) sample document (`sample_sow_contract.txt`). Initial attempts to run the pipeline uncovered several dependency issues, serialization bugs, and API rate limits. 

Here are the step-by-step findings and the applied fixes.

## 1. Dependency Error: `packaging.version.InvalidVersion`
**Issue**: Upon importing `build_pipeline()`, LangGraph crashed with `packaging.version.InvalidVersion: Invalid version: '2.12.5'`.
**Root Cause**: The project was using the latest `packaging` library (`v26.0`), which strictly enforces PEP 440 and rejected the `pydantic` version string format. Older versions of Langchain-core's internals were incompatible with this strictness.
**Fix**: Downgraded the `packaging` module.
```bash
./venv/bin/pip install "packaging==23.2"
```

## 2. Dependency Error: `No module named '_cffi_backend'`
**Issue**: The `load_and_preprocess` node failed while trying to import `pdfplumber` (which relies on `cryptography` and `cffi`).
**Root Cause**: The Python environment had a corrupted or incompatible binary build of the C-extension for `_cffi_backend`.
**Fix**: Force re-installed the affected libraries to rebuild the native extensions for the current architecture.
```bash
./venv/bin/pip install --force-reinstall cffi cryptography
```

## 3. Diffbot API Error: `400 Bad Request`
**Issue**: The Diffbot extraction node failed because the API rejected the HTTP request.
**Root Cause**: The URL parameter `fields` was being serialized as a JSON string (`["entities", "facts"]`). The Diffbot API expects a comma-separated string (`entities,facts`).
**Fix**: Updated `app/extraction/diffbot_client.py` to join the fields using commas instead of `json.dumps()`.
```python
# Modified app/extraction/diffbot_client.py => _call_diffbot()
params={"token": DIFFBOT_API_TOKEN, "fields": ",".join(fields)},
```

## 4. LangChain Template Error in LLM Mapper
**Issue**: The `map_with_llm` node crashed with `missing variables {'short_name', 'NodeType', '\n  "Client"'}`.
**Root Cause**: The `SYSTEM_PROMPT` in `app/mapper/llm_mapper.py` contained JSON representations of the property schema (e.g., `{ "Client": { ... } }`). Langchain's `ChatPromptTemplate` interpreted these literal curly braces as variables requiring interpolation.
**Fix**: Wrapped the system prompt inside a static `SystemMessage` object so LangChain skips variable interpolation for that section.
```python
# Modified app/mapper/llm_mapper.py => map_section_with_llm()
from langchain_core.messages import SystemMessage
prompt = ChatPromptTemplate.from_messages(
    [SystemMessage(content=SYSTEM_PROMPT), ("human", HUMAN_TEMPLATE)]
)
```

## 5. API Rate Limits (Groq & Gemini)
**Issue**: Because the sample document was broken into 11 sections by the preprocessor, the LLM mapper attempted to call the LLM API 11 times in rapid succession.
- **Groq**: Retrying indefinitely due to strict Requests-Per-Minute (RPM) limits on the Llama 3 70B model.
- **Gemini**: Switching to Gemini resulted in `429 RESOURCE_EXHAUSTED` due to the Google API Free Tier limit of 15 Requests Per Minute. 

**Root Cause**: Processing large documents page-by-page or section-by-section generates heavy concurrency that easily breaches free-tier API quotas.
**Fix/Recommendation**: The code handles this gracefully via LangChain's automatic retry backoffs, but the execution time becomes very high. To resolve this for production use, you must configure a paid-tier API key (OpenAI, Anthropic, or paid Gemini/Groq), or introduce proactive batching/sleep delays in `llm_mapper.py`.

## Summary of Results
Despite the API rate-limiting delays at the LLM mapping stage, the underlying pipeline transitions are fully functional:
- The custom SOW was accurately preprocessed and segmented into 11 sections.
- Diffbot successfully extracted entities and facts for all chunks.
- The `test_pipeline_run.py` successfully emulated an end-to-end LangGraph stream, successfully navigating the Human-in-The-Loop review interrupts.
