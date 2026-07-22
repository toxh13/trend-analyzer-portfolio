package com.example.backendspring.dto;

import jakarta.validation.Validation;
import jakarta.validation.Validator;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Set;
import java.util.stream.Collectors;

import static org.assertj.core.api.Assertions.assertThat;

class CrawlingRequestDtoValidationTest {

    private final Validator validator = Validation.buildDefaultValidatorFactory().getValidator();

    @Test
    void rejectsMissingFieldsAtHttpRequestBoundary() {
        CrawlingRequestDto request = new CrawlingRequestDto(
                " ",
                "",
                null,
                "",
                null,
                null,
                List.of()
        );

        Set<String> invalidFields = validator.validate(request).stream()
                .map(violation -> violation.getPropertyPath().toString())
                .collect(Collectors.toSet());

        assertThat(invalidFields).containsExactlyInAnyOrder(
                "title", "summary", "sourceUrl", "source", "category", "publishedAt"
        );
    }
}
