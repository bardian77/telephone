export default function About() {
  return (
    <article className="reading">
      <h1>Why I am doing this</h1>
      <p className="lead">
        A photograph matters because it is specific: this place, this light, this person. The systems that carry photographs
        now keep what is typical and drop what is specific. Telephone shows that happening to my own photographs, one pass at
        a time, and names what goes first.
      </p>
      <p>
        The name comes from the children’s game, where a sentence is whispered from one person to the next and comes out
        changed. Here the thing being passed along is a photograph, and the people in the line are the systems that handle
        pictures online: the app that shrinks an upload, the phone that takes a screenshot, the machine that describes a
        picture in words and the machine that draws one from a description.
      </p>
      <p>
        The photo you send is not the photo that arrives. If you make photographs, the parts you worked for are often the
        fragile ones. I wanted to see that with pictures I care about, and to measure it, so that I am not only describing a
        feeling.
      </p>
      <p>
        Telephone is my Experimentation Portfolio for <i>5IMAG022W The Networked Photograph</i> at the University of
        Westminster. I am Bardia Nasab.
      </p>

      <h2>Where it comes from</h2>
      <ul className="ref">
        <li>
          Pete Ashton, <i>I Am Sitting in Stagram</i> (2015). One photograph reposted to Instagram 90 times, each repost a
          screenshot of the last. The closest ancestor of the first half of this project, and itself a tribute to:
        </li>
        <li>
          Alvin Lucier, <i>I Am Sitting in a Room</i> (1969). A voice re-recorded in a room until only the room’s resonance is
          left. The channel becomes the subject.
        </li>
        <li>
          Hito Steyerl, <i>In Defense of the Poor Image</i> (2009). The compressed, copied, low-resolution image is the image
          that actually circulates.
        </li>
        <li>
          Hito Steyerl, <i>Mean Images</i> (2023). It gives the project its claim: if pictures made by these systems are
          averages of what they were trained on, a photograph passed through them should lose what is specific first.
        </li>
        <li>
          Trevor Paglen, <i>Invisible Images (Your Pictures Are Looking at You)</i> (2016). Most images are now made for and
          read by machines. The place measurement on this site is one small case of a machine reading my pictures.
        </li>
        <li>
          Ilia Shumailov and others, <i>AI models collapse when trained on recursively generated data</i>, Nature (2024). When
          a generating system is fed its own output, the rare details go first. That predicts what should disappear first when
          the describe-and-redraw loop is run.
        </li>
        <li>
          Thomas Ruff, <i>jpegs</i> (2004 onwards), and Rosa Menkman, <i>Glitch Studies Manifesto</i> (2010). Compression as
          something to look at, not only something to hide.
        </li>
      </ul>

      <h2>Ethics</h2>
      <ul>
        <li>Every starting picture is a photograph I took. The person in the self-portrait is me.</li>
        <li>People in the street photographs are small and cannot be identified.</li>
        <li>
          If you try your own photo on this site, it stays on your device. The page works inside your browser. Nothing is
          uploaded and nothing is stored.
        </li>
        <li>
          No picture on this site was made by an AI. When the describe-and-redraw loop is run, its pictures will be shown as
          results and labelled as machine-made.
        </li>
        <li>
          Some AI services may keep what is sent to them. Only my own photographs will be sent through them.
        </li>
      </ul>
    </article>
  )
}
