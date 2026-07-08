# Deploying to Atenea / Moodle (LTI 1.1)

This tool is an LTI 1.1 **External Tool**. These steps are for Moodle 4.x
(Atenea is UPC's Moodle); other LMSes are similar.

## 1. Deploy the tool over HTTPS

The tool must be reachable over **HTTPS** — the launch cookie uses
`SameSite=None; Secure`, which browsers only honour on HTTPS, and Atenea
embeds the tool in an iframe. Put it behind your reverse proxy / institution
hostname and set in `.env`:

```
PUBLIC_BASE_URL=https://your-tool.example.edu
```

## 2. Create the External Tool in Moodle

As a teacher (or site admin, for a site-wide tool):

**Site administration → Plugins → Activity modules → External tool →
Manage tools → configure a tool manually**, or add an External Tool
activity directly in a course.

| Field | Value |
|---|---|
| Tool name | e.g. "AI Chat Activity" |
| Tool URL | `https://your-tool.example.edu/lti/launch` |
| LTI version | **LTI 1.0/1.1** |
| Consumer key | the value of `LTI_CONSUMER_KEY` in your `.env` |
| Shared secret | the value of `LTI_SECRET` in your `.env` |
| Default launch container | Embed, or New window |
| **Privacy** | Share launcher's name **and** email: *Always* — the tool uses them for the roster and grade attribution |
| **Privacy** | Accept grades from the tool: *Always* — required for passback |

## 3. Add the activity to a course

Add an **External Tool** activity in a course and select the tool you
configured. Set the activity to accept grades if you want passback into the
gradebook.

## 4. First launch (instructor)

The first time you (as instructor) open the activity, you land on the
tool's **setup** page: give it a title, pick the LAMB assistant, and choose
whether grades pass back. Save. From then on the activity opens on the
dashboard.

## 5. Students

Students opening the activity get the chatbot bound to the assistant you
chose. If you enabled grading, their grades appear in your dashboard; press
**Send saved grades to LMS** to push them into the Moodle gradebook.

## Troubleshooting

- **"Launch rejected" (401).** Consumer key or secret mismatch between
  Moodle and `.env`, or `PUBLIC_BASE_URL` doesn't match the URL Moodle
  actually used (proxy rewriting the host). The signature is computed over
  that URL — it must match exactly.
- **Blank iframe / session lost between pages.** The tool must be on HTTPS
  for the `Secure` cookie; the header/query-param session fallbacks cover
  most iframe cases, but HTTPS is required regardless.
- **Grades don't appear.** Confirm "Accept grades from the tool" is on in
  the tool config, and that the activity itself has a grade type set. The
  tool only has a passback URL for students whose launch carried
  `lis_outcome_service_url` — check the launch privacy settings.
