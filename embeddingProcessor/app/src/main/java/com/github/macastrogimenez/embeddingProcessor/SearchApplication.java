package com.github.macastrogimenez.embeddingProcessor;

import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.context.annotation.Bean;

@SpringBootApplication
public class SearchApplication{
    
    @Bean 
    public EmbeddingService embeddingService (){
        return new EmbeddingService();
    }

    @Bean (initMethod = "initializeCollection", destroyMethod = "close")
    public MilvusRepository vectorDb (){
        return new MilvusRepository(false);
    }

}