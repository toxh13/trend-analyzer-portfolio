package com.example.backendspring.config;


import io.swagger.v3.oas.models.OpenAPI;
import io.swagger.v3.oas.models.info.Info;
import org.springframework.context.annotation.Configuration;

@Configuration
public class SwaggerConfig {

    public OpenAPI customOpenAPI() {
        return new OpenAPI()
                .info(new Info()
                        .title("트렌드 분석 API")
                        .version("1.0")
                        .description("트렌드 분석 API 명세서"));
    }
}
