export default function About() {
  return (
    <>
      <h1>About</h1>
      <p>
        <b>Telephone</b> is the Experimentation Portfolio for <i>5IMAG022W The Networked Photograph</i> (University of Westminster).
        It is a practice-led experiment: my own photographs are passed repeatedly through the systems that circulate and interpret
        images online, and at every step the pipeline measures what drifts and what survives.
      </p>
      <h2>The loop</h2>
      <ol>
        <li><b>Platform.</b> Resize, re-encode as JPEG at a platform's quality, strip metadata. What an upload does.</li>
        <li><b>Caption.</b> A vision-language model (Claude Sonnet 5.5 by default) writes a description.</li>
        <li><b>Regenerate.</b> A text-to-image model (Gemini 2.5 Flash Image or FLUX.1 schnell) recreates the picture from the description.</li>
      </ol>
      <p>The output becomes the next generation's input. Chains run for 10 to 20 generations.</p>
      <h2>Measurement</h2>
      <ul>
        <li><b>Drift.</b> Cosine distance between CLIP ViT-B/32 embeddings of each generation and the original, plus a colour-histogram distance that needs no model, plus SSIM and LPIPS for compression-only chains.</li>
        <li><b>Survival.</b> A vision model fills a fixed JSON schema for every generation (objects, people count, visible text, setting, lighting, mood, dominant colours, camera angle, reads-as-photograph). Each field is compared with generation 0 under stated rules; the generation where a field first fails is the result.</li>
        <li><b>Machine readability.</b> OCR word count and face-detector count per generation.</li>
        <li><b>Validation.</b> Hand labels on a fixed sample of 60 pairs, collected on the Label page, compared against the automated measures.</li>
      </ul>
      <h2>Context</h2>
      <ul className="ref">
        <li>Pete Ashton, <i>I Am Sitting in Stagram</i> (2015): one photograph reposted to Instagram 90 times, each time from a screenshot of the last. The direct ancestor of this project's method, itself a tribute to:</li>
        <li>Alvin Lucier, <i>I Am Sitting in a Room</i> (1969): a voice re-recorded through a room until only the room's resonance remains.</li>
        <li>Hito Steyerl, <i>In Defense of the Poor Image</i> (2009): circulation degrades images and that degradation is itself meaningful.</li>
        <li>Ilia Shumailov et al., <i>AI models collapse when trained on recursively generated data</i>, Nature (2024): recursion through generative models loses the tails of the distribution first.</li>
        <li>Trevor Paglen, <i>Invisible Images (Your Pictures Are Looking at You)</i> (2016) and Kate Crawford and Trevor Paglen, <i>Excavating AI</i> (2019): images made for machines, and what machine readings get wrong.</li>
        <li>Thomas Ruff, <i>jpegs</i> (2004 onwards) and Rosa Menkman, <i>Glitch Studies Manifesto</i> (2010): compression as a visible aesthetic.</li>
      </ul>
      <h2>Ethics</h2>
      <p>
        Only photographs I took are used as starting images. Identifiable people appear only with consent. Nothing visitors upload
        is stored: the live demo, where enabled, works on my photographs only and deletes nothing because it keeps nothing.
        Free-tier model providers may use inputs to improve their services; that is why only my own images go through them.
        Generated images carry provider watermarks where the provider adds them.
      </p>
      <h2>Code</h2>
      <p>
        Everything is open: <a href="https://github.com/bardian77/telephone">github.com/bardian77/telephone</a>. The pipeline is a Python
        package with provider adapters, a content-addressed cache, a hard spend cap and a run ledger; this site is a static view of that ledger.
      </p>
    </>
  )
}
