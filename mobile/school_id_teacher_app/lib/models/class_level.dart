class SectionOption {
  final int id;
  final String name;
  final int classLevelId;

  SectionOption({
    required this.id,
    required this.name,
    required this.classLevelId,
  });

  factory SectionOption.fromJson(Map<String, dynamic> json) {
    return SectionOption(
      id: json['id'] ?? 0,
      name: json['name'] ?? '',
      classLevelId: json['class_level'] ?? 0,
    );
  }
}

class ClassLevelOption {
  final int id;
  final String name;
  final int numericOrder;
  final List<SectionOption> sections;

  ClassLevelOption({
    required this.id,
    required this.name,
    required this.numericOrder,
    required this.sections,
  });

  factory ClassLevelOption.fromJson(Map<String, dynamic> json) {
    var rawSections = json['sections'] as List? ?? [];
    List<SectionOption> sectionsList =
        rawSections.map((s) => SectionOption.fromJson(s as Map<String, dynamic>)).toList();

    return ClassLevelOption(
      id: json['id'] ?? 0,
      name: json['name'] ?? '',
      numericOrder: json['numeric_order'] ?? 0,
      sections: sectionsList,
    );
  }
}
