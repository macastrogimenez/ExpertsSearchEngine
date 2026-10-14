package com.github.macastrogimenez.embeddingProcessor;

import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.ResultSet;
import java.sql.Statement;
import java.lang.StringBuilder;


public class Main {
    public static void main(String[] args) throws Exception {

        String host = System.getenv("DB_HOST");
        String database = System.getenv("DB_NAME");
        String username = System.getenv("DB_USERNAME");
        String password = System.getenv("DB_PASSWORD");

        String url =
                "jdbc:aws-wrapper:postgresql://" +
                host +
                ":5432/" +
                database;

        try (Connection connection =
                    DriverManager.getConnection(
                            url,
                            username,
                            password)) 
                    {

                        System.out.println("Connected!");

                        try (
                                Statement statement = connection.createStatement();
                                ResultSet result =
                                    statement.executeQuery("SELECT current_database(), current_user");
                            )
                            {
                                while (result.next()) {
                                    System.out.println(
                                            "Database: " + result.getString(1)
                                    );
                                    System.out.println(
                                            "User: " + result.getString(2)
                                    );
                                }
                            }    
                        try(
                            Statement statement = connection.createStatement();
                            ResultSet result2 = statement.executeQuery("SELECT * FROM prod.person");
                        ) 
                        {

                            while (result2.next()) {
                                StringBuilder s = new StringBuilder();
                                for (int i = 1; i < 7; i++) {
                                    if (i<6){
                                        s.append(result2.getString(i)+" || ");
                                    }else{
                                        s.append(result2.getString(i));
                                        System.out.println(s.toString());
                                    }
                                }
                            }
                        }                    
                    }
    }
}
