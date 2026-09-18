#ifndef uLidFvPatchVectorField_H
#define uLidFvPatchVectorField_H

#include "fixedValueFvPatchFields.H"

namespace Foam
{

class uLidFvPatchVectorField
:
    public fixedValueFvPatchVectorField
{
public:

    TypeName("uLid");

    uLidFvPatchVectorField
    (
        const fvPatch&,
        const DimensionedField<vector, volMesh>&
    );

    uLidFvPatchVectorField
    (
        const fvPatch&,
        const DimensionedField<vector, volMesh>&,
        const dictionary&
    );

    uLidFvPatchVectorField
    (
        const uLidFvPatchVectorField&,
        const fvPatch&,
        const DimensionedField<vector, volMesh>&,
        const fvPatchFieldMapper&
    );

    uLidFvPatchVectorField(const uLidFvPatchVectorField&) = delete;

    uLidFvPatchVectorField
    (
        const uLidFvPatchVectorField&,
        const DimensionedField<vector, volMesh>&
    );

    virtual tmp<fvPatchVectorField> clone
    (
        const DimensionedField<vector, volMesh>& iF
    ) const
    {
        return tmp<fvPatchVectorField>
        (
            new uLidFvPatchVectorField(*this, iF)
        );
    }

    virtual void updateCoeffs();

    virtual void write(Ostream&) const;
};

} // End namespace Foam

#endif
