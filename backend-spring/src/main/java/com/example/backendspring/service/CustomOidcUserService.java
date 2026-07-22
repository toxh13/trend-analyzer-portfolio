package com.example.backendspring.service;

import com.example.backendspring.entity.User;
import com.example.backendspring.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.oauth2.client.oidc.userinfo.OidcUserRequest;
import org.springframework.security.oauth2.client.oidc.userinfo.OidcUserService;
import org.springframework.security.oauth2.core.OAuth2AuthenticationException;
import org.springframework.security.oauth2.core.oidc.user.DefaultOidcUser;
import org.springframework.security.oauth2.core.oidc.user.OidcUser;
import org.springframework.stereotype.Service;

import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;

@Service
@RequiredArgsConstructor
public class CustomOidcUserService extends OidcUserService {

    private final UserRepository userRepository;

    @Override
    public OidcUser loadUser(OidcUserRequest userRequest) throws OAuth2AuthenticationException {
        OidcUser oidcUser = super.loadUser(userRequest);
        String registrationId = userRequest.getClientRegistration().getRegistrationId();

        // Google은 openid scope를 사용하므로 OAuth2UserService가 아니라 OidcUserService 경로로 사용자 정보가 들어옵니다.
        // 여기에서 DB 사용자 저장 후 internalUserId를 principal attributes에 추가해야 /api/v1/auth/me가 로그인 사용자를 찾을 수 있습니다.
        SocialProfile profile = extractProfile(registrationId, oidcUser.getAttributes());
        User user = saveOrUpdateUser(profile);

        Map<String, Object> attributes = new HashMap<>(oidcUser.getAttributes());
        attributes.put("internalUserId", user.getId());
        attributes.put("provider", user.getProvider());
        attributes.put("providerId", user.getProviderId());
        attributes.put("email", user.getEmail());
        attributes.put("username", user.getUsername());
        attributes.put("role", user.getRole());

        return new DefaultOidcUser(
                List.of(new SimpleGrantedAuthority(user.getRole())),
                oidcUser.getIdToken(),
                oidcUser.getUserInfo(),
                profile.nameAttributeKey()
        ) {
            @Override
            public Map<String, Object> getAttributes() {
                return attributes;
            }

            @Override
            public Object getAttribute(String name) {
                return attributes.get(name);
            }
        };
    }

    private SocialProfile extractProfile(String registrationId, Map<String, Object> attributes) {
        if ("google".equalsIgnoreCase(registrationId)) {
            return new SocialProfile(
                    "GOOGLE",
                    String.valueOf(attributes.get("sub")),
                    (String) attributes.get("email"),
                    (String) attributes.getOrDefault("name", attributes.get("email")),
                    "sub"
            );
        }

        throw new OAuth2AuthenticationException("Unsupported OIDC provider: " + registrationId);
    }

    private User saveOrUpdateUser(SocialProfile profile) {
        Optional<User> socialUser = userRepository.findByProviderAndProviderId(profile.provider(), profile.providerId());

        User user = socialUser
                // 같은 이메일의 기존 웹 계정이 있으면 소셜 제공자 정보를 연결합니다.
                .or(() -> profile.email() == null ? Optional.<User>empty() : userRepository.findFirstByEmail(profile.email()))
                .orElseGet(User::new);

        user.setProvider(profile.provider());
        user.setProviderId(profile.providerId());
        user.setEmail(profile.email());
        user.setUsername(profile.username());
        user.setRole(user.getRole() == null ? "ROLE_USER" : user.getRole());

        return userRepository.save(user);
    }

    private record SocialProfile(
            String provider,
            String providerId,
            String email,
            String username,
            String nameAttributeKey
    ) {
    }
}
