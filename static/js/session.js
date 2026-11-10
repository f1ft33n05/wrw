const fetchWithSessionHandling = window.fetch.bind(window);
let sessionRedirectStarted = false;

window.fetch = async (...args) => {
    const response = await fetchWithSessionHandling(...args);
    if (
        response.status === 401
        && response.headers.get("X-Session-Expired") === "true"
        && !sessionRedirectStarted
    ) {
        sessionRedirectStarted = true;
        const returnPath = `${window.location.pathname}${window.location.search}${window.location.hash}`;
        const loginUrl = new URL("/", window.location.origin);
        loginUrl.searchParams.set("session_expired", "1");
        loginUrl.searchParams.set("next", returnPath);
        window.location.replace(loginUrl);
    }
    return response;
};
