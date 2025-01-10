// to minify into a bookmarklet, use https://skalman.github.io/UglifyJS-online/

// SCRIPT START:
var height = document.body.scrollHeight;
/**
 * A Map that contains the video URL as its key, and the video caption as its value
 */
var linksMap = new Map([]);

function loadWebpage() {
  // If items from the DOM are removed, the page must be scrolled a little bit higher, so that the TikTok refresh is triggered
  window.scrollTo({
    top: document.body.scrollHeight - window.outerHeight,
    behavior: "smooth",
  });

  // Checks if the SVG loading animation is present in the DOM
  setTimeout(() => {
    window.scrollTo({
      top: document.body.scrollHeight,
      behavior: "smooth",
    }); // Scroll to the bottom of the page
    setTimeout(() => {
      if (height !== document.body.scrollHeight) {
        // The webpage has scrolled the previous time, so we can try another scroll
        addArray();
        setTimeout(() => {
          height = document.body.scrollHeight;
          loadWebpage();
        }, Math.floor(Math.random() * 500 + 10));
      } else {
        setTimeout(() => {
          if (
            !document.querySelector(
              "#main-content-others_homepage .css-qmnyxf-SvgContainer"
            ) &&
            height == document.body.scrollHeight
          ) {
            ytDlpScript();
          } else {
            // The SVG animation is still there, so there are other contents to load.
            loadWebpage();
          }
        }, 1000);
      }
    }, 150);
  }, Math.floor(Math.random() * 600 + 600));
}
/**
 * Elaborate items in the page
 */
function addArray() {
  const selectors = "a[href*='/video/'], a[href*='/photo/']";
  const container = Array.from(document.querySelectorAll(selectors));
  for (const tikTokItem of container) {
    const getLink = tikTokItem.href;
    if (!tikTokItem) continue; // Skip nullish results

    if ((getLink ?? "") === "") {
      // If the script needs to check if the link is nullish, and it's nullish...
      console.log("SCRIPT ERROR: Failed to get link!"); // If the user wants to print the error in the console, write it
      continue; // And, in general, continue with the next link.
    }
    console.log(getLink);
    linksMap.set(getLink, {});
  }

  console.log(`Links found: ${linksMap.size}`);

  // Delete all the items from the DOM. Only the last 20 items will be kept.
  for (const item of Array.from(container).slice(0, container.length - 20))
    item.remove();
}

function ytDlpScript() {
  addArray();
  let ytDlpScript = "";
  for (const [url] of Array.from(linksMap)) {
    ytDlpScript += `${url}\n`;
  }
  downloadScript(ytDlpScript);
}

function downloadScript(script) {
  const blob = new Blob([script], { type: "text/plain" });
  const link = document.createElement("a");
  const name = `${
    document.querySelector("h1")?.textContent.trim() ?? "TikTokLinks"
  }.txt`;

  link.href = URL.createObjectURL(
    new File([blob], name, { type: "text/plain" })
  );
  link.download = name;
  link.click();
  URL.revokeObjectURL(link.href);
}
function startDownload(name) {
  linksMap = new Map([]);
  loadWebpage(); // And start scrolling the webpage
}
startDownload();
