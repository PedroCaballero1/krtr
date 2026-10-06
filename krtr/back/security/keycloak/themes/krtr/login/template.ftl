<#--
  Layout of every krtr login page, after the login screen of docs/krtr diseño.html: a header with
  the brand and the ES/PT switch, then two columns, the page title on the left and the form on the
  right. Same macro and sections as base's template.ftl, plus an optional "intro" section for the
  text under the title. Base's session checks are kept; its PatternFly-only markup is not.
-->
<#macro registrationLayout bodyClass="" displayInfo=false displayMessage=true displayRequiredFields=false>
<!DOCTYPE html>
<html lang="${lang}">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="robots" content="noindex, nofollow">
    <title>${msg("loginTitle",(realm.displayName!''))}</title>
    <link rel="icon" type="image/png" href="${url.resourcesPath}/img/krtr-logo.png">
    <#if properties.styles?has_content>
        <#list properties.styles?split(' ') as style>
            <link href="${url.resourcesPath}/${style}" rel="stylesheet">
        </#list>
    </#if>
    <#if scripts??>
        <#list scripts as script>
            <script src="${script}" type="text/javascript"></script>
        </#list>
    </#if>
    <script type="importmap">
        {
            "imports": {
                "rfc4648": "${url.resourcesCommonPath}/vendor/rfc4648/rfc4648.js"
            }
        }
    </script>
    <script type="module">
        <#outputformat "JavaScript">
        import { startSessionPolling } from ${(url.resourcesPath + "/js/authChecker.js")?c};

        startSessionPolling(
            ${url.ssoLoginInOtherTabsUrl?c}
        );
        </#outputformat>
    </script>
    <#if authenticationSession??>
        <script type="module">
            <#outputformat "JavaScript">
            import { checkAuthSession } from ${(url.resourcesPath + "/js/authChecker.js")?c};

            checkAuthSession(
                ${authenticationSession.authSessionIdHash?c}
            );
            </#outputformat>
        </script>
    </#if>
</head>

<body class="krtr ${bodyClass}" data-page-id="login-${pageId}">
<header class="krtr-nav">
    <span class="krtr-brand">
        <img class="krtr-brand-logo" src="${url.resourcesPath}/img/krtr-logo.png" alt="">
        <span>${realm.displayName!'krtr'}</span>
    </span>
    <#if realm.internationalizationEnabled && locale.supported?size gt 1>
        <nav class="krtr-locale" id="kc-locale" aria-label="${msg("languages")}">
            <#list locale.supported as l>
                <a href="${l.url}" lang="${l.languageTag}" title="${l.label}"
                   <#if l.languageTag == locale.currentLanguageTag>aria-current="true"</#if>>${l.languageTag?keep_before("-")?upper_case}</a>
            </#list>
        </nav>
    </#if>
</header>

<main class="krtr-main">
    <section class="krtr-intro">
        <h1 id="kc-page-title"><#nested "header"></h1>
        <#nested "intro">
    </section>

    <section class="krtr-panel" id="kc-content">
        <#if auth?has_content && auth.showUsername() && !auth.showResetCredentials()>
            <#nested "show-username">
            <div id="kc-username" class="krtr-username">
                <span id="kc-attempted-username">${auth.attemptedUsername}</span>
                <a id="reset-login" href="${url.loginRestartFlowUrl}">${msg("restartLoginTooltip")}</a>
            </div>
        </#if>

        <#if displayRequiredFields>
            <p class="krtr-hint"><span class="required">*</span> ${msg("requiredFields")}</p>
        </#if>

        <#-- App-initiated actions should not see warning messages about the need to complete the action during login. -->
        <#if displayMessage && message?has_content && (message.type != 'warning' || !isAppInitiatedAction??)>
            <div class="krtr-alert krtr-alert-${message.type}" role="alert">${kcSanitize(message.summary)?no_esc}</div>
        </#if>

        <#nested "form">

        <#if auth?has_content && auth.showTryAnotherWayLink()>
            <form id="kc-select-try-another-way-form" action="${url.loginAction}" method="post">
                <input type="hidden" name="tryAnotherWay" value="on">
                <button type="submit" class="krtr-btn krtr-btn-link">${msg("doTryAnotherWay")}</button>
            </form>
        </#if>

        <#nested "socialProviders">

        <#if displayInfo>
            <div id="kc-info" class="krtr-info">
                <#nested "info">
            </div>
        </#if>
    </section>
</main>
</body>
</html>
</#macro>
