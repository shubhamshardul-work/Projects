# 🚀 Build Your Own Free Subscription Backend (No Server Needed)

Since you are hosting on GitHub Pages (which is a static site without a database), we cannot securely write to an Excel file sitting in the repository from a public website without exposing your GitHub passwords.

**The Solution:** We turn a standard **Google Sheet** (Excel) into a free serverless backend using **Google Apps Script**. 

This script accepts emails directly from your website, checks if the email already exists (preventing duplicates), and saves it to the Sheet. Your Python agent then reads directly from this sheet!

---

### Step 1: Create the "Excel" Database
1. Go to [Google Sheets](https://sheets.google.com) and create a new blank spreadsheet.
2. Name it `GenAI Subscribers`.
3. In **Cell A1**, type `Date Joined`.
4. In **Cell B1**, type `Email Address`.

*(This exactly matches how your `nodes.py` Python script reads emails from Column 2!)*

### Step 2: Add the Backend Code
1. In your Google Sheet, click on **Extensions** > **Apps Script** in the top menu.
2. Delete any code in the editor, and paste the following code exactly:

```javascript
function doPost(e) {
  var sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
  
  // We expect an 'email' parameter from the frontend website
  var email = e.parameter.email;
  
  if (!email) {
    return ContentService.createTextOutput(JSON.stringify({"result": "error", "error": "Email missing"}))
      .setMimeType(ContentService.MimeType.JSON);
  }
  
  email = email.toLowerCase().trim();
  
  // Deduplication Check: Read existing emails in Column B (Index 1)
  var data = sheet.getDataRange().getValues();
  for (var i = 1; i < data.length; i++) { // Start at 1 to skip header row
    if (data[i][1] && data[i][1].toLowerCase().trim() === email) {
      return ContentService.createTextOutput(JSON.stringify({"result": "success", "message": "Already subscribed"}))
        .setMimeType(ContentService.MimeType.JSON); // We return success so the frontend UI looks good
    }
  }
  
  // If email is new, append it as a new row: [Date, Email]
  sheet.appendRow([new Date(), email]);
  
  return ContentService.createTextOutput(JSON.stringify({"result": "success", "message": "Email added successfully"}))
    .setMimeType(ContentService.MimeType.JSON);
}
```

### Step 3: Publish the API (Crucial Step)

1. Click the blue **Deploy** button at the top right, and select **New deployment**.
2. Click the gear icon ⚙️ next to "Select type" and choose **Web app**.
3. Fill in the details exactly like this:
   - **Description**: `Subscription API`
   - **Execute as**: `Me (your email)`
   - **Who has access**: `Anyone` *(This is important!)*
4. Click **Deploy**.
5. Google will ask you to authorize access. Click **Authorize access**, choose your account, click **Advanced**, and click **Go to Untitled project (unsafe)**. Then click **Allow**.
6. **COPY the "Web app URL"** provided in the final screen. It will look like `https://script.google.com/macros/s/.../exec`.

---

### Step 4: Link It to Your Website

I have already updated your website's code to use this new system! You just need to paste your new Web App URL into the code:

1. Open `/Users/shardulmac/Documents/Projects/Projects/site-src/app.js` in your code editor.
2. Scroll to the very bottom (around line 253).
3. Replace the placeholder URL with the **Web app URL** you just copied:
```javascript
const url = 'PASTE_YOUR_GOOGLE_APPS_SCRIPT_WEB_APP_URL_HERE'; 
```
4. Commit and push! 

That’s it! Your website will now securely funnel subscriptions directly into your private Google Sheet without any duplicates, bypassing Google Forms entirely.
