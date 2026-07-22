package com.example.backendspring.service;

import com.example.backendspring.entity.User;
import com.example.backendspring.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.oauth2.client.userinfo.DefaultOAuth2UserService;
import org.springframework.security.oauth2.client.userinfo.OAuth2UserRequest;
import org.springframework.security.oauth2.core.OAuth2AuthenticationException;
import org.springframework.security.oauth2.core.user.DefaultOAuth2User;
import org.springframework.security.oauth2.core.user.OAuth2User;
import org.springframework.stereotype.Service;

import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;

@Service
@RequiredArgsConstructor
public class CustomOAuth2UserService extends DefaultOAuth2UserService {

    private final UserRepository userRepository;

    @Override
    public OAuth2User loadUser(OAuth2UserRequest userRequest) throws OAuth2AuthenticationException {
        OAuth2User oauthUser = super.loadUser(userRequest);
        String registrationId = userRequest.getClientRegistration().getRegistrationId();

        // 현재는 Google 우선 구현입니다. 이후 kakao/naver가 추가되면 이 메서드의 분기만 확장합니다.
        SocialProfile profile = extractProfile(registrationId, oauthUser.getAttributes());
        User user = saveOrUpdateUser(profile);

        Map<String, Object> attributes = new HashMap<>(oauthUser.getAttributes());
        attributes.put("internalUserId", user.getId());
        attributes.put("provider", user.getProvider());
        attributes.put("providerId", user.getProviderId());
        attributes.put("email", user.getEmail());
        attributes.put("username", user.getUsername());
        attributes.put("role", user.getRole());

        return new DefaultOAuth2User(
                List.of(new SimpleGrantedAuthority(user.getRole())),
                attributes,
                profile.nameAttributeKey()
        );
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

        throw new OAuth2AuthenticationException("Unsupported OAuth2 provider: " + registrationId);
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
