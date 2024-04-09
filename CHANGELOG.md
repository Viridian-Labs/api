### Changelog v2 



1. **Enhanced Caching**:
    - In v2, there's a clear emphasis on caching, which is intended to improve HTTP response times. By caching frequently accessed data, the application can serve subsequent requests faster, as they no longer have to fetch or compute the same data repeatedly. Multi-thread approach
2. **Data Source Priority**:
    - v2 introduces the capability to determine the order of data retrieval from internal and external sources. Users can select which source is prioritized, ensuring flexibility in the way data is fetched. This is crucial for situations where one data source might be more reliable, faster, or cost-effective than the other.
3. **Configurability and Extensibility**:
    - The refactor introduces several new options, allowing users or developers to tailor the application's behavior to specific needs. This shows a move towards making the application more configurable and adaptable to different scenarios.
4. **Improved Error Handling**:
    - The added error handlers in v2 indicate a robust approach to managing unexpected scenarios. This not only improves the resilience of the application but also provides meaningful error messages or fallbacks when things go awry.
5. **Enhanced Documentation**:
    - The inclusion of function documentation suggests that v2 emphasizes clarity and maintainability. Well-documented code is easier for developers to understand, modify, and extend, making the entire codebase more sustainable in the long run.
6. **Environment Configurations**:
    - The `.env` files have likely seen modifications or enhancements to accommodate the new features and changes in v2. These files typically hold crucial configurations that dictate the behavior and environment-specific settings of the application.
7. **Modular Approach**:
    - The clear division into modules (`viri`, `assets`, `pairs`) in v2 suggests a more modular design, making the application more organized and easier to manage.
8. **Code Structure and Classes**:
    - The introduction of new classes and modifications to existing ones would indicate a shift in the application's logic, structure, and potentially its core functionalities. By redefining classes and their methods, v2 is likely providing more refined, efficient, or extended functionalities compared to v1.