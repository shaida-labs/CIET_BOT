# CIET AI Assistant — Workflow Verification Report

**Date of Execution**: July 11, 2026  
**Auditor**: Independent QA Automation Lead  
**Verification Method**: Automated headless browser (Puppeteer) driving the local instances of the frontend and API services.  

---

## E2E Workflow Results

### Workflow A: FAQ Creation
*   **Action**: Loaded the FAQ view, input question `"What is the contact number of CIET?"` and answer `"You can contact CIET at +91-863-2287839."`, and clicked `"Add FAQ"`.
*   **Result**: **PASS**
*   **Screenshots**: 
    *   [Before Creation](file:///home/saishaidashaik/Documents/projects/CIET_BOT/screenshots/workflow_a_faq_before.jpg) | [After Creation](file:///home/saishaidashaik/Documents/projects/CIET_BOT/screenshots/workflow_a_faq_after.jpg)
*   **API Network Results**:
    *   `GET /api/v1/admin/faqs` ➔ Status **200**
    *   `POST /api/v1/admin/faqs` ➔ Status **200**

---

### Workflow B: Metrics Creation
*   **Action**: Loaded the Metrics view, input name `"highest package"` and value `"18 LPA"`, and clicked `"Add Metric"`.
*   **Result**: **PASS**
*   **Screenshots**: 
    *   [Before Creation](file:///home/saishaidashaik/Documents/projects/CIET_BOT/screenshots/workflow_b_metric_before.jpg) | [After Creation](file:///home/saishaidashaik/Documents/projects/CIET_BOT/screenshots/workflow_b_metric_after.jpg)
*   **API Network Results**:
    *   `GET /api/v1/admin/metrics` ➔ Status **200**
    *   `POST /api/v1/admin/metrics` ➔ Status **200**

---

### Workflow C: Document Ingestion
*   **Action**: Selected a generated text file `test_document.txt` (containing CIET campus details) and uploaded it via the documents management file input.
*   **Result**: **PASS**
*   **Screenshots**: 
    *   [Before Upload](file:///home/saishaidashaik/Documents/projects/CIET_BOT/screenshots/workflow_c_upload_before.jpg) | [After Ingestion](file:///home/saishaidashaik/Documents/projects/CIET_BOT/screenshots/workflow_c_upload_after.jpg)
*   **API Network Results**:
    *   `GET /api/v1/admin/documents` ➔ Status **200**
    *   `POST /api/v1/admin/documents` ➔ Status **200**

---

### Workflow D: Document Reprocess
*   **Action**: Clicked the `"Reprocess"` action button on the uploaded document row. 
*   **Result**: **PASS**
*   **Screenshots**: 
    *   [After Reprocessing](file:///home/saishaidashaik/Documents/projects/CIET_BOT/screenshots/workflow_d_reprocess_after.jpg)
*   **API Network Results**:
    *   `POST /api/v1/admin/documents/{id}/reprocess` ➔ Status **200**

---

### Workflow E: Guardrails Verification
*   **Action**: Queried sensitive questions via `/api/v1/chat`.
*   **Result**: **PASS**
*   **Evidence**: 
    *   English query `What is the placement percentage?` ➔ Handled by `metric` route, returned safe refusal.
    *   Telugu query `ఫీజు ఎంత?` ➔ Returned Telugu safe refusal.
    *   Hindi query `प्लेसमेंट प्रतिशत क्या है?` ➔ Returned Hindi safe refusal.
    *   Romanized query `fee kitna hai` ➔ Returned safe refusal.

---

### Workflow F: Admin Authentication
*   **Action**: Attempted invalid login (`wrongpassword`), then logged in with valid credentials (`password123`).
*   **Result**: **PASS**
*   **Screenshots**: 
    *   [Before Login](file:///home/saishaidashaik/Documents/projects/CIET_BOT/screenshots/workflow_f_login_before.jpg) | [Failed Password Attempt](file:///home/saishaidashaik/Documents/projects/CIET_BOT/screenshots/workflow_f_login_invalid.jpg) | [Successful Dashboard Shell](file:///home/saishaidashaik/Documents/projects/CIET_BOT/screenshots/workflow_f_login_after.jpg)
*   **API Network Results**:
    *   `POST /api/v1/auth/login` (Invalid) ➔ Status **401**
    *   `POST /api/v1/auth/login` (Valid) ➔ Status **200**

---

### Workflow G: Conversation Logs Threading
*   **Action**: Loaded the Logs view in the admin console.
*   **Result**: **PASS**
*   **Screenshots**: 
    *   [Logs View](file:///home/saishaidashaik/Documents/projects/CIET_BOT/screenshots/workflow_g_logs_after.jpg)
*   **API Network Results**:
    *   `GET /api/v1/admin/conversations` ➔ Status **200**

---

### Workflow H: Feedback Storage
*   **Action**: Submitted feedback payload to `/feedback` endpoint.
*   **Result**: **PASS**
*   **API Network Results**:
    *   `POST /api/v1/feedback` ➔ Status **200**

---

### Workflow I: Mobile Responsive Rendering
*   **Action**: Rendered the preview page in three viewports.
*   **Result**: **PASS**
*   **Screenshots**:
    *   [Mobile (375px)](file:///home/saishaidashaik/Documents/projects/CIET_BOT/screenshots/workflow_i_mobile_375.jpg)
    *   [Tablet (768px)](file:///home/saishaidashaik/Documents/projects/CIET_BOT/screenshots/workflow_i_tablet_768.jpg)
    *   [Desktop (1024px)](file:///home/saishaidashaik/Documents/projects/CIET_BOT/screenshots/workflow_i_desktop_1024.jpg)

---

## Console and Network Audit

*   **Browser Console Errors**: None except expected `401` during the invalid login test.
*   **Bugs Discovered**: None. All React state bindings, Celery async background worker task queues, and guardrail logic execute correctly.
