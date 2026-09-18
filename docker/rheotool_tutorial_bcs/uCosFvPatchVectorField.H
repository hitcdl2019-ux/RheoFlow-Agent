#ifndef uCosFvPatchVectorField_H
#define uCosFvPatchVectorField_H

#include "fixedValueFvPatchFields.H"

namespace Foam
{

class uCosFvPatchVectorField
:
    public fixedValueFvPatchVectorField
{
    scalar tlim_;
    scalar fac_;
    vector uav_;
    vector dirN_;

public:

    TypeName("uCos");

    uCosFvPatchVectorField
    (
        const fvPatch&,
        const DimensionedField<vector, volMesh>&
    );

    uCosFvPatchVectorField
    (
        const fvPatch&,
        const DimensionedField<vector, volMesh>&,
        const dictionary&
    );

    uCosFvPatchVectorField
    (
        const uCosFvPatchVectorField&,
        const fvPatch&,
        const DimensionedField<vector, volMesh>&,
        const fvPatchFieldMapper&
    );

    uCosFvPatchVectorField(const uCosFvPatchVectorField&) = delete;

    uCosFvPatchVectorField
    (
        const uCosFvPatchVectorField&,
        const DimensionedField<vector, volMesh>&
    );

    virtual tmp<fvPatchVectorField> clone
    (
        const DimensionedField<vector, volMesh>& iF
    ) const
    {
        return tmp<fvPatchVectorField>
        (
            new uCosFvPatchVectorField(*this, iF)
        );
    }

    virtual void updateCoeffs();

    virtual void write(Ostream&) const;
};

} // End namespace Foam

#endif
