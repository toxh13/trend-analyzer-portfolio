package com.example.backendspring;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.data.jpa.repository.config.EnableJpaAuditing;
import org.springframework.scheduling.annotation.EnableScheduling;
import org.springframework.scheduling.annotation.EnableAsync;
import org.springframework.web.bind.annotation.CrossOrigin;

@EnableJpaAuditing
@EnableScheduling
@EnableAsync
@SpringBootApplication
public class BackendSpringApplication {

    public static void main(String[] args) {
        SpringApplication.run(BackendSpringApplication.class, args);
    }

}
