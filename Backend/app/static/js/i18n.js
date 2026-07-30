(() => {
  const STORAGE_KEY = "forgeos-language";
  const FALLBACK_LANGUAGE = "en";
  const SUPPORTED = ["en", "fa"];
  const dictionaries = {};

  async function loadDictionary(language) {
    if (dictionaries[language]) return dictionaries[language];
    const response = await fetch(`/static/i18n/${language}.json`);
    if (!response.ok) throw new Error(`Unable to load ${language} translations`);
    dictionaries[language] = await response.json();
    return dictionaries[language];
  }

  function setText(element, value) {
    if (element.dataset.i18nHtml === "true") element.innerHTML = value;
    else element.textContent = value;
  }

  async function setLanguage(language) {
    const selected = SUPPORTED.includes(language) ? language : FALLBACK_LANGUAGE;
    const dictionary = await loadDictionary(selected);
    document.documentElement.lang = selected;
    document.documentElement.dir = selected === "fa" ? "rtl" : "ltr";
    document.body?.classList.toggle("locale-fa", selected === "fa");
    document.querySelectorAll("[data-i18n]").forEach((element) => {
      const key = element.dataset.i18n;
      if (dictionary[key]) setText(element, dictionary[key]);
    });
    document.querySelectorAll("[data-i18n-attr]").forEach((element) => {
      const [attribute, key] = element.dataset.i18nAttr.split(":");
      if (attribute && key && dictionary[key]) element.setAttribute(attribute, dictionary[key]);
    });
    document.querySelectorAll("[data-lang-label]").forEach((element) => {
      element.classList.toggle("text-cyan-300", element.dataset.langLabel === selected);
      element.classList.toggle("text-slate-500", element.dataset.langLabel !== selected);
    });
    localStorage.setItem(STORAGE_KEY, selected);
    window.dispatchEvent(new CustomEvent("forge:language", { detail: { language: selected, dictionary } }));
    return selected;
  }

  window.forgeI18n = {
    get language() {
      return localStorage.getItem(STORAGE_KEY) || FALLBACK_LANGUAGE;
    },
    setLanguage,
    async init() {
      return setLanguage(this.language);
    },
  };
  window.forgeI18n.init().catch((error) => console.warn("ForgeOS i18n unavailable", error));
})();
