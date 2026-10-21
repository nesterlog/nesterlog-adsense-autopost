/* IGNIPLEX Related Posts 썸네일 수정
 * 위치: 테마 HTML → /* ** ADDITIONAL SCRIPT START FROM HERE ** */ 안쪽에 붙여넣기
 * 원인: Related는 media$thumbnail만 보는데, Unsplash 외부 이미지는 이 값이 없음
 * 방법: 전체 글 피드에서 첫 <img>를 찾아 Related의 noimage를 교체
 */
(function () {
  function firstImg(html) {
    if (!html) return null;
    var m = String(html).match(/<img[^>]+src=["']([^"']+)["']/i);
    return m ? m[1].replace(/&amp;/g, "&") : null;
  }

  function isBroken(src) {
    if (!src) return true;
    src = String(src);
    return (
      src.indexOf("igniplex-noimage") !== -1 ||
      src.indexOf("data:image") === 0 ||
      src.indexOf("AAAA") !== -1 && src.indexOf("base64") !== -1
    );
  }

  function buildMap(data) {
    var map = {};
    var entries = (data && data.feed && data.feed.entry) || [];
    entries.forEach(function (e) {
      var links = e.link || [];
      var alt = null;
      for (var i = 0; i < links.length; i++) {
        if (links[i].rel === "alternate") {
          alt = links[i].href;
          break;
        }
      }
      if (!alt) return;
      var src =
        (e["media$thumbnail"] && e["media$thumbnail"].url) ||
        firstImg(e.content && e.content.$t) ||
        firstImg(e.summary && e.summary.$t);
      if (!src) return;
      map[alt] = src;
      map[alt.replace(/\/$/, "")] = src;
    });
    return map;
  }

  function apply(map) {
    var roots = document.querySelectorAll(
      ".related-middle, .related-bottom, .related-middle-inner, .related-bottom-inner"
    );
    roots.forEach(function (root) {
      root.querySelectorAll("a[href]").forEach(function (a) {
        var href = a.href;
        var src = map[href] || map[href.replace(/\/$/, "")];
        if (!src) return;
        var img = a.querySelector("img");
        if (!img) return;
        var cur = img.getAttribute("data-src") || img.getAttribute("src") || "";
        if (!isBroken(cur) && cur.indexOf("unsplash") === -1 && cur.indexOf("http") === 0) {
          return;
        }
        img.setAttribute("data-src", src);
        img.setAttribute("src", src);
        img.classList.remove("lazy");
        img.classList.add("lazyloaded");
      });
    });
  }

  function run() {
    fetch("/feeds/posts/default?alt=json&max-results=50")
      .then(function (r) {
        return r.json();
      })
      .then(function (data) {
        var map = buildMap(data);
        apply(map);
        var obs = new MutationObserver(function () {
          apply(map);
        });
        obs.observe(document.body, { childList: true, subtree: true });
        setTimeout(function () {
          apply(map);
        }, 1200);
        setTimeout(function () {
          apply(map);
        }, 3000);
      })
      .catch(function () {});
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", run);
  } else {
    run();
  }
})();
