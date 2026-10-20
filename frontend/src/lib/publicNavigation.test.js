import {
  getHashTargetId,
  hasActiveSpecials,
  scrollToHashTarget,
} from "./publicNavigation";

describe("public-site navigation", () => {
  afterEach(() => {
    document.body.innerHTML = "";
  });

  test("shows the Specials link only when active specials exist", () => {
    expect(hasActiveSpecials()).toBe(false);
    expect(hasActiveSpecials([])).toBe(false);
    expect(hasActiveSpecials([{ id: "special-1" }])).toBe(true);
  });

  test("normalizes plain and encoded fragment identifiers", () => {
    expect(getHashTargetId("#catering-quote")).toBe("catering-quote");
    expect(getHashTargetId("#Sandwiches%20%26%20Po%27Boys")).toBe(
      "Sandwiches & Po'Boys",
    );
    expect(getHashTargetId("")).toBe("");
  });

  test("scrolls an existing fragment target into view", () => {
    document.body.innerHTML = '<section id="catering-quote"></section>';
    const target = document.getElementById("catering-quote");
    target.scrollIntoView = jest.fn();

    expect(scrollToHashTarget("#catering-quote")).toBe(true);
    expect(target.scrollIntoView).toHaveBeenCalledWith({
      behavior: "auto",
      block: "start",
    });
  });

  test("does not scroll when the fragment target is absent", () => {
    expect(scrollToHashTarget("#specials")).toBe(false);
    expect(scrollToHashTarget("")).toBe(false);
  });
});
