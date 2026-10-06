<#--
  The krtr sign-in form, after the login screen of docs/krtr diseño.html: customer number and
  password, an "Enter" button with an arrow and the lockout hint. The realm has no registration,
  password reset, remember-me or identity providers (task 3.2), so base's markup for them is left
  out.
-->
<#import "template.ftl" as layout>
<@layout.registrationLayout displayMessage=!messagesPerField.existsError('username','password'); section>
    <#if section = "header">
        ${msg("loginAccountTitle")}
    <#elseif section = "intro">
        <p class="krtr-lead">${msg("krtrLoginBody")}</p>
    <#elseif section = "form">
        <#if realm.password>
            <form id="kc-form-login" class="krtr-form" onsubmit="login.disabled = true; return true;" action="${url.loginAction}" method="post">
                <#if messagesPerField.existsError('username','password')>
                    <div id="input-error" class="krtr-alert krtr-alert-error" role="alert" aria-live="polite">
                        ${kcSanitize(messagesPerField.getFirstError('username','password'))?no_esc}
                    </div>
                </#if>

                <#if !usernameHidden??>
                    <div class="krtr-field">
                        <label for="username" class="krtr-label">${msg("username")}</label>
                        <input id="username" class="krtr-input krtr-input-lg krtr-input-code" name="username" value="${(login.username!'')}" type="text"
                               autofocus autocomplete="username" autocapitalize="characters" spellcheck="false" dir="ltr"
                               aria-invalid="<#if messagesPerField.existsError('username','password')>true</#if>">
                    </div>
                </#if>

                <div class="krtr-field">
                    <label for="password" class="krtr-label">${msg("password")}</label>
                    <input id="password" class="krtr-input krtr-input-lg" name="password" type="password" autocomplete="current-password" dir="ltr"
                           <#if usernameHidden??>autofocus</#if>
                           aria-invalid="<#if messagesPerField.existsError('username','password')>true</#if>">
                </div>

                <input type="hidden" id="id-hidden-input" name="credentialId" <#if auth.selectedCredential?has_content>value="${auth.selectedCredential}"</#if>>
                <button class="krtr-btn krtr-btn-primary krtr-btn-cta" name="login" id="kc-login" type="submit">
                    <span>${msg("doLogIn")}</span>
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M5 12h14"></path><path d="m12 5 7 7-7 7"></path></svg>
                </button>
                <p class="krtr-hint">${msg("krtrLoginHint")}</p>
            </form>
        </#if>
    </#if>
</@layout.registrationLayout>
