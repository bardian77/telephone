// "How it works": the project explained from the idea down to the engineering.
// Plain HTML strings. Edited with the humanizer rules: no number or metric name is changed by it.

export const KEY_INFO = {
  ANTHROPIC_API_KEY: "Claude. The default Reader, and the model that fills in the survival form.",
  GEMINI_API_KEY: "Gemini. The default Painter.",
  CLOUDFLARE_ACCOUNT_ID: "Cloudflare Workers AI. The second Painter in the swap experiment.",
  CLOUDFLARE_API_TOKEN: "Cloudflare Workers AI. Needed together with the account ID.",
  REPLICATE_API_TOKEN: "Replicate. An optional Painter.",
  OPENAI_API_KEY: "OpenAI. An optional Reader and Painter.",
};

export const STATIONS = [
  {
    kind: "platform",
    role: "Platform",
    text: "Does what an upload to Instagram or WhatsApp does. It shrinks the picture, re-saves it as a JPEG at the platform’s quality, and strips the hidden metadata.",
  },
  {
    kind: "caption",
    role: "Reader",
    text: "An AI vision model looks at the picture and writes a description of it in words.",
  },
  {
    kind: "regenerate",
    role: "Painter",
    text: "An AI image model draws a new picture from that description alone. It never sees the photograph.",
  },
];

export function guideHtml(patch) {
  const station = (s) =>
    `<li><span class="patch" data-kind="${s.kind}"></span><span><b>${s.role}.</b> ${s.text}</span></li>`;
  return `
  <header class="page-head">
    <h1>How Telephone works</h1>
    <p class="lead">Five levels, from the idea to the engineering. Stop wherever you have enough.</p>
    <nav class="toc" aria-label="On this page">
      <a href="#/guide?to=idea">The idea</a>
      <a href="#/guide?to=loop">The loop</a>
      <a href="#/guide?to=measure">What is measured</a>
      <a href="#/guide?to=read">Reading a result</a>
      <a href="#/guide?to=built">How it is built</a>
      <a href="#/guide?to=words">Glossary</a>
    </nav>
  </header>

  <section class="level" id="idea">
    <p class="level-tag">Level 1</p>
    <h2>The idea</h2>
    <p>In the children’s game Telephone, a sentence is whispered from one person to the next and comes out the other end changed. This project plays that game with a photograph. The photo is handed to a system that handles pictures, the result is handed on again, and this repeats 12 or 20 times. After every hand-off the result is compared with the original.</p>
    <p>The question is what a photograph keeps and what it loses on the way. The photographs are of real places (the Bologna porticoes, the Barbican, the Dolomites), so the sharper form of the question is whether a place stays that place, or turns into a generic European street and a generic concrete building.</p>
  </section>

  <section class="level" id="loop">
    <p class="level-tag">Level 2</p>
    <h2>The loop</h2>
    <p>A photograph can pass through three kinds of station. Each has its own colour everywhere in this dashboard.</p>
    <ul class="loop-detail">${STATIONS.map(station).join("")}</ul>
    <p>A <b>chain</b> is one photograph plus a chosen list of stations, run round and round. Each trip round is one <b>generation</b>. Generation 0 is the original, generation 1 is what comes out after one trip.</p>
    <p>An <b>experiment</b> asks one question by running several versions of the loop on every photograph. Experiment 1 uses the Platform station only, four ways. That is the baseline: it shows how much damage plain uploading does before any AI is involved. The later experiments add the Reader and the Painter.</p>
  </section>

  <section class="level" id="measure">
    <p class="level-tag">Level 3</p>
    <h2>What is measured</h2>
    <p>Two things are measured at every generation.</p>
    <p><b>Drift</b> is how far the picture has moved from the original, as one number. It comes from CLIP, an image-recognition model that turns a picture into a list of numbers describing what it shows. Two identical pictures are 0 apart. Two different photographs from this project are about 0.43 apart. The grey step wedge you see next to every result places the drift between those two anchors, so 0.09 reads as “21% of the way to a different photograph”.</p>
    <p>The four names on the wedge (same, worn, drifting, different) are a rule of thumb chosen by hand to make the position easier to say out loud. They are not measured thresholds.</p>
    <p><b>Survival</b> is which facts about the picture are still true. A vision model fills in the same form for every generation: the objects in it, the number of people, any readable text, where it is, the lighting, the mood, the main colours, the camera angle, and whether it still looks like a photograph. Each answer is compared with the answer for the original. A fact that stops matching has died, and the generation where that happens is recorded. The survival form needs a vision model, so it needs an API key.</p>
    <p>Three supporting measures are recorded as well. SSIM compares pixel structure, where 1 means identical and one Instagram-style upload scores about 0.99. LPIPS is a learned measure of how different two pictures look to people, where 0 means identical. The colour distance compares the mix of colours and needs no model at all.</p>
  </section>

  <section class="level" id="read">
    <p class="level-tag">Level 4</p>
    <h2>Reading a result</h2>
    <p>A run produces one picture per generation and one row of measurements per picture. The Results pages turn those rows into three things: the pictures side by side with the original, the position on the step wedge, and a chart of drift over the generations.</p>
    <ul>
      <li>A line that jumps once and then runs flat means the loop found a resting point. Experiment 1 found this on all six photographs: under a fixed platform setting, all of the change happens on the first upload, because re-saving a JPEG at the same size and quality gives back almost the same JPEG.</li>
      <li>A line that keeps climbing means every trip does new damage. That is what the describe-and-redraw loop is expected to do. It has not been run for real yet.</li>
      <li>On the survival form, the first fact to die shows what the loop treats as disposable. Small readable text and the exact number of people are the usual candidates.</li>
      <li>A result marked “Simulation” came from stand-in models. It shows how the loop works and says nothing about real photographs.</li>
    </ul>
    <p>Previews in the dashboard are resized so pages load quickly. To judge compression damage by eye, open the actual file from the link under each picture.</p>
  </section>

  <section class="level" id="built">
    <p class="level-tag">Level 5</p>
    <h2>How it is built</h2>
    <ul>
      <li><b>The ledger.</b> Every generation is one row in a local database, <code>data/ledger.sqlite</code>, holding the models, settings, seed, measurements and cost. The figures, this dashboard and the public website all read from it.</li>
      <li><b>The cache.</b> A station’s output is stored under a key made from the input picture, the station’s settings, the model and the seed. Running the same step again costs nothing.</li>
      <li><b>The fingerprint.</b> A chain resumes only from rows made with the same stations, models and seed, so a simulation can never be continued as a real run.</li>
      <li><b>The spend cap.</b> Every paid call is logged. A call that would take the total over the cap is refused before it is made.</li>
      <li><b>Experiment files.</b> Each experiment is a short YAML file in <code>experiments/</code> listing the versions of the loop to run.</li>
      <li><b>Where the output goes.</b> Pictures are written to <code>data/runs/</code>, one folder per chain. A snapshot of an experiment’s rows can be saved to <code>data/results/</code>, which is the part that is committed to Git.</li>
    </ul>
    <p>Everything this dashboard does is also a terminal command. <code>telephone --help</code> lists them.</p>
  </section>

  <section class="level" id="words">
    <h2>Glossary</h2>
    <dl class="glossary">
      <div><dt>Station</dt><dd>One step a picture goes through: Platform, Reader or Painter.</dd></div>
      <div><dt>Chain</dt><dd>One photograph plus an ordered list of stations, run round and round.</dd></div>
      <div><dt>Generation</dt><dd>One trip round the loop. Generation 0 is the original.</dd></div>
      <div><dt>Version</dt><dd>One named list of stations inside an experiment, such as the harsh platform setting. The experiment files call it a variant.</dd></div>
      <div><dt>Drift</dt><dd>How far a generation has moved from the original. 0 is identical; about 0.43 is a different photograph.</dd></div>
      <div><dt>Survival</dt><dd>Which answers on the survival form still match the original, and when each one stopped matching.</dd></div>
      <div><dt>CLIP</dt><dd>The image-recognition model used to measure drift.</dd></div>
      <div><dt>SSIM</dt><dd>A comparison of pixel structure. 1 means identical.</dd></div>
      <div><dt>LPIPS</dt><dd>A learned measure of how different two pictures look. 0 means identical.</dd></div>
      <div><dt>Simulation</dt><dd>A run on stand-in models that cost nothing. Its output is never a result.</dd></div>
      <div><dt>Ledger</dt><dd>The local database with one row per generation.</dd></div>
    </dl>
  </section>`;
}
